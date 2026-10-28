"""
python manage.py simulate [--tps 2] [--session SESSION_ID]

Continuously generates realistic transactions, scores them with the ML model,
saves them to the DB, and broadcasts results over WebSockets in real time.

Ctrl-C stops the simulation gracefully.
"""
import sys
import time
import signal
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand
from django.db import connection as db_conn

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'detection' / 'ml'
sys.path.insert(0, str(ML_DIR))

HOLD_THRESHOLD   = 0.75   # auto-hold transactions above this probability
FREEZE_THRESHOLD = 3      # auto-freeze account after this many confirmed fraud hits


class Command(BaseCommand):
    help = 'Run the real-time transaction simulation and fraud detection engine'

    def add_arguments(self, parser):
        parser.add_argument('--tps',     type=float, default=2.0,
                            help='Transactions per second (default: 2)')
        parser.add_argument('--session', type=int,   default=None,
                            help='Resume an existing SimulationSession ID')

    def handle(self, *args, **options):
        from preprocess import preprocess_inference_data
        from predict   import predict_dataframe, get_fraud_reason
        from simulation.generator import generate_transaction
        from simulation.models    import SimulationSession
        from dashboard.models     import Transaction, FraudAlert, AccountStatus, ReviewQueue
        from simulation.consumers import _auto_freeze

        tps          = options['tps']
        interval     = 1.0 / tps
        channel_layer = get_channel_layer()

        # ── Session setup ────────────────────────────────────────────────
        if options['session']:
            session = SimulationSession.objects.get(pk=options['session'])
            session.status = 'running'
            session.save()
        else:
            session = SimulationSession.objects.create(tps=tps)

        self.stdout.write(self.style.SUCCESS(
            f'\n🚀  MoMo Shield Simulator started — Session #{session.pk} — {tps} TPS\n'
            f'    Press Ctrl-C to stop.\n'
        ))

        # ── Graceful shutdown ────────────────────────────────────────────
        running = [True]
        def _stop(sig, frame):
            running[0] = False
            self.stdout.write('\n⏹  Stopping simulator…')
        signal.signal(signal.SIGINT,  _stop)
        signal.signal(signal.SIGTERM, _stop)

        total = 0
        fraud = 0

        while running[0]:
            loop_start = time.time()
            db_conn.close()   # fresh connection each loop (thread safety)

            try:
                raw = generate_transaction()

                # ── Check if sender/receiver account is frozen ────────────
                sender_frozen   = AccountStatus.objects.filter(
                    account_number=raw['sender'],   status='frozen').exists()
                receiver_frozen = AccountStatus.objects.filter(
                    account_number=raw['receiver'], status='frozen').exists()

                if sender_frozen or receiver_frozen:
                    blocked_by = 'sender' if sender_frozen else 'receiver'
                    _broadcast(channel_layer, 'simulation_feed', 'simulation_transaction', {
                        'txn_id':          raw['txn_id'],
                        'sender':          raw['sender'],
                        'receiver':        raw['receiver'],
                        'amount':          raw['amount_ugx'],
                        'txn_type':        raw['txn_type'],
                        'channel':         raw['channel'],
                        'fraud_prob':      1.0,
                        'risk_level':      'blocked',
                        'status':          'BLOCKED',
                        'reason':          f'Account frozen ({blocked_by})',
                        'held':            False,
                        'timestamp':       raw['_timestamp'],
                    })
                    total += 1
                    _update_session(session, total, fraud)
                    _sleep(interval, loop_start)
                    continue

                # ── Preprocess & score ────────────────────────────────────
                df = pd.DataFrame([raw])
                X, df_e = preprocess_inference_data(df)
                result  = predict_dataframe(X)
                prob    = result['probabilities'][0]
                pred    = result['predictions'][0]
                row     = df_e.iloc[0].to_dict()

                risk = ('high'   if prob >= 0.75 else
                        'medium' if prob >= 0.40 else 'low')
                is_fraud_flag = bool(pred)
                reason = get_fraud_reason(row, prob) if is_fraud_flag else ''

                # ── Determine action ──────────────────────────────────────
                # High-probability fraud → HOLD for human review
                on_hold = is_fraud_flag and prob >= HOLD_THRESHOLD
                status  = 'HOLD' if on_hold else ('FRAUD' if is_fraud_flag else 'CLEAN')

                # ── Save to DB ────────────────────────────────────────────
                txn = Transaction.objects.create(
                    transaction_id    = raw['txn_id'],
                    sender            = raw['sender'],
                    receiver          = raw['receiver'],
                    amount            = raw['amount_ugx'],
                    transaction_type  = raw['txn_type'],
                    is_fraud          = is_fraud_flag,
                    fraud_score       = round(prob, 4),
                    fraud_probability = round(prob, 4),
                    timestamp         = datetime.now(timezone.utc),
                )

                if is_fraud_flag:
                    fraud += 1
                    FraudAlert.objects.create(
                        transaction=txn, severity=risk, reason=reason
                    )
                    # Increment fraud hit counter; auto-freeze if threshold reached
                    sender_acc   = _auto_freeze(raw['sender'],   None, reason)
                    receiver_acc = _auto_freeze(raw['receiver'],  None, reason)

                    # Broadcast freeze events if triggered
                    for acc in [sender_acc, receiver_acc]:
                        if acc.status == 'frozen':
                            _broadcast(channel_layer, 'account_status', 'account_update', {
                                'account':   acc.account_number,
                                'status':    'frozen',
                                'hit_count': acc.fraud_hit_count,
                                'reason':    acc.notes,
                            })

                    if on_hold:
                        ReviewQueue.objects.create(transaction=txn, auto_held=True)
                        # Broadcast to review queue group
                        _broadcast(channel_layer, 'review_queue', 'review_update', {
                            'event':    'new_hold',
                            'txn_id':   raw['txn_id'],
                            'sender':   raw['sender'],
                            'receiver': raw['receiver'],
                            'amount':   raw['amount_ugx'],
                            'prob':     round(prob, 4),
                            'reason':   reason,
                        })

                total += 1

                # ── Broadcast transaction to live feed ────────────────────
                _broadcast(channel_layer, 'simulation_feed', 'simulation_transaction', {
                    'txn_id':    raw['txn_id'],
                    'sender':    raw['sender'],
                    'receiver':  raw['receiver'],
                    'amount':    raw['amount_ugx'],
                    'txn_type':  raw['txn_type'],
                    'channel':   raw['channel'],
                    'fraud_prob': round(prob, 4),
                    'risk_level': risk,
                    'status':    status,
                    'reason':    reason,
                    'held':      on_hold,
                    'timestamp': raw['_timestamp'],
                    'session_total': total,
                    'session_fraud': fraud,
                })

                _update_session(session, total, fraud)

                if total % 20 == 0:
                    self.stdout.write(
                        f'  [{datetime.now().strftime("%H:%M:%S")}] '
                        f'{total:>6} txns | {fraud:>4} fraud '
                        f'({fraud/total*100:.1f}%)'
                    )

            except Exception as e:
                logger.exception("Simulator error on transaction %s", total)
                self.stderr.write(f'  ⚠ Error: {e}')

            _sleep(interval, loop_start)

        # ── Shutdown ─────────────────────────────────────────────────────
        session.status     = 'stopped'
        session.stopped_at = datetime.now(timezone.utc)
        session.save()
        self.stdout.write(self.style.SUCCESS(
            f'\n✓  Simulation stopped. Total: {total} txns, {fraud} fraud '
            f'({fraud/total*100:.1f}% rate)' if total else '\n✓  Stopped.'
        ))


def _broadcast(channel_layer, group, msg_type, data):
    """Fire-and-forget broadcast to a channel group."""
    try:
        async_to_sync(channel_layer.group_send)(group, {'type': msg_type, 'data': data})
    except Exception as e:
        logger.debug("Broadcast error: %s", e)


def _update_session(session, total, fraud):
    SimulationSession = session.__class__
    SimulationSession.objects.filter(pk=session.pk).update(
        total_generated=total, total_fraud=fraud
    )


def _sleep(interval, loop_start):
    elapsed = time.time() - loop_start
    remaining = interval - elapsed
    if remaining > 0:
        time.sleep(remaining)
