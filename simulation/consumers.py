"""
MoMo Shield — WebSocket Consumer
==================================
Handles the live simulation feed over WebSocket.

Channel group: "simulation_feed"  — broadcasts every scored transaction.
Channel group: "review_queue"     — broadcasts review queue updates.
Channel group: "account_status"   — broadcasts account freeze/clear events.
"""
import json
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent / 'detection' / 'ml'
sys.path.insert(0, str(ML_DIR))

# Auto-hold threshold — transactions above this probability are put on hold
HOLD_THRESHOLD   = 0.75
# Auto-freeze threshold — account frozen after this many fraud hits
FREEZE_THRESHOLD = 3


class SimulationConsumer(AsyncWebsocketConsumer):
    """WebSocket endpoint: /ws/simulation/"""

    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return
        await self.channel_layer.group_add('simulation_feed', self.channel_name)
        await self.channel_layer.group_add('review_queue',    self.channel_name)
        await self.channel_layer.group_add('account_status',  self.channel_name)
        await self.accept()
        logger.info("WS connected: %s", self.channel_name)

    async def disconnect(self, code):
        await self.channel_layer.group_discard('simulation_feed', self.channel_name)
        await self.channel_layer.group_discard('review_queue',    self.channel_name)
        await self.channel_layer.group_discard('account_status',  self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Handle control messages from the browser."""
        try:
            msg = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return

        action = msg.get('action')
        if action == 'review_decision':
            await self._handle_review_decision(msg)
        elif action == 'freeze_account':
            await self._handle_freeze(msg)
        elif action == 'unfreeze_account':
            await self._handle_unfreeze(msg)

    # ── Group message handlers (called by channel layer) ──────────────────

    async def simulation_transaction(self, event):
        await self.send(text_data=json.dumps({'type': 'transaction', **event['data']}))

    async def review_update(self, event):
        await self.send(text_data=json.dumps({'type': 'review_update', **event['data']}))

    async def account_update(self, event):
        await self.send(text_data=json.dumps({'type': 'account_update', **event['data']}))

    # ── Control handlers ──────────────────────────────────────────────────

    async def _handle_review_decision(self, msg):
        txn_id   = msg.get('txn_id')
        decision = msg.get('decision')   # 'confirmed' or 'cleared'
        note     = msg.get('note', '')
        if not txn_id or decision not in ('confirmed', 'cleared'):
            return

        result = await self._save_review_decision(txn_id, decision, note, self.scope['user'])
        await self.channel_layer.group_send('review_queue', {
            'type': 'review_update',
            'data': {'txn_id': txn_id, 'decision': decision, 'note': note, **result},
        })

    async def _handle_freeze(self, msg):
        account = msg.get('account')
        note    = msg.get('note', 'Manual freeze by analyst')
        if not account:
            return
        result = await self._freeze_account(account, self.scope['user'], note)
        await self.channel_layer.group_send('account_status', {
            'type': 'account_update',
            'data': {'account': account, 'status': 'frozen', **result},
        })

    async def _handle_unfreeze(self, msg):
        account = msg.get('account')
        if not account:
            return
        result = await self._unfreeze_account(account, self.scope['user'])
        await self.channel_layer.group_send('account_status', {
            'type': 'account_update',
            'data': {'account': account, 'status': 'cleared', **result},
        })

    # ── DB helpers (run in thread pool via database_sync_to_async) ───────

    @database_sync_to_async
    def _save_review_decision(self, txn_id, decision, note, user):
        from dashboard.models import ReviewQueue, AccountStatus
        try:
            rq = ReviewQueue.objects.select_related('transaction').get(
                transaction__transaction_id=txn_id
            )
            rq.decision     = decision
            rq.analyst      = user
            rq.analyst_note = note
            rq.decided_at   = datetime.now(timezone.utc)
            rq.save()

            # If confirmed fraud — also freeze both accounts
            if decision == 'confirmed':
                _auto_freeze(rq.transaction.sender,   user, 'Confirmed fraud — analyst decision')
                _auto_freeze(rq.transaction.receiver, user, 'Confirmed fraud — analyst decision')

            return {'success': True, 'amount': str(rq.transaction.amount)}
        except ReviewQueue.DoesNotExist:
            return {'success': False, 'error': 'Review queue item not found'}

    @database_sync_to_async
    def _freeze_account(self, account, user, note):
        return _freeze_account_sync(account, user, note)

    @database_sync_to_async
    def _unfreeze_account(self, account, user):
        from dashboard.models import AccountStatus
        acc, _ = AccountStatus.objects.get_or_create(account_number=account)
        acc.status     = 'cleared'
        acc.cleared_at = datetime.now(timezone.utc)
        acc.notes      = 'Manually cleared by analyst'
        acc.save()
        return {'success': True}


# ── Sync helpers (called from both consumer and simulator thread) ─────────────

def _freeze_account_sync(account: str, user, note: str) -> dict:
    from dashboard.models import AccountStatus
    acc, _ = AccountStatus.objects.get_or_create(account_number=account)
    if acc.status != 'frozen':
        acc.status    = 'frozen'
        acc.frozen_by = user if hasattr(user, 'pk') else None
        acc.frozen_at = datetime.now(timezone.utc)
        acc.notes     = note
        acc.save()
    return {'success': True, 'hit_count': acc.fraud_hit_count}


def _auto_freeze(account: str, user, reason: str):
    """Increment fraud hit count and freeze if threshold reached."""
    from dashboard.models import AccountStatus
    acc, _ = AccountStatus.objects.get_or_create(account_number=account)
    acc.fraud_hit_count += 1
    if acc.fraud_hit_count >= FREEZE_THRESHOLD and acc.status != 'frozen':
        acc.status    = 'frozen'
        acc.frozen_by = user if hasattr(user, 'pk') else None
        acc.frozen_at = datetime.now(timezone.utc)
        acc.notes     = f'Auto-frozen: {acc.fraud_hit_count} fraud hits. {reason}'
    elif acc.status == 'active':
        acc.status = 'flagged'
    acc.save()
    return acc
