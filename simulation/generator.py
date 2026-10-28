"""
MoMo Shield — Transaction Generator
====================================
Generates realistic synthetic MTN/Airtel Uganda mobile money transactions.
Fraud typologies mirror the training data distribution.
"""
import random
import string
import uuid
from datetime import datetime, timezone


# ── Uganda-realistic pools ────────────────────────────────────────────────────
MTN_PREFIXES    = ['0770', '0771', '0772', '0773', '0774', '0775', '0776', '0777', '0778']
AIRTEL_PREFIXES = ['0700', '0701', '0702', '0703', '0704', '0750', '0751', '0752', '0753']
CHANNELS        = ['USSD', 'App', 'Agent']
CHANNEL_WEIGHTS = [0.55, 0.30, 0.15]

TXN_TYPES = [
    'Send Money', 'Withdraw', 'Deposit', 'Pay Bill',
    'Buy Goods', 'Bank Transfer', 'Airtime',
]
TXN_WEIGHTS = [0.35, 0.20, 0.15, 0.12, 0.10, 0.05, 0.03]

# Fraud typologies (must sum to 1.0)
FRAUD_TYPES = [
    'sim_swap',          # 40 % — SIM-swap account drain
    'agent_float',       # 30 % — Agent float theft
    'social_engineering',# 20 % — Social engineering
    'account_takeover',  # 10 % — Account takeover burst
]
FRAUD_WEIGHTS = [0.40, 0.30, 0.20, 0.10]

# Base fraud rate (~7 %, matching training data)
BASE_FRAUD_RATE = 0.07

# Known bad accounts (simulates repeat offenders)
_bad_receivers: list[str] = []


def _phone(prefixes=None):
    if prefixes is None:
        prefixes = MTN_PREFIXES + AIRTEL_PREFIXES
    p = random.choice(prefixes)
    return p + ''.join(random.choices(string.digits, k=6))


def _txn_id():
    return 'SIM-' + uuid.uuid4().hex[:12].upper()


def _amount_legit():
    """Legitimate: log-normal, centred around UGX 50 000."""
    base = random.lognormvariate(10.8, 1.2)
    # Round to nearest 500 (common in Uganda)
    if random.random() < 0.45:
        base = round(base / 500) * 500
    return max(500, min(base, 9_000_000))


def _amount_fraud(typology: str):
    """Fraud amounts tend to be large and often round."""
    if typology == 'sim_swap':
        amt = random.uniform(800_000, 4_000_000)
    elif typology == 'agent_float':
        amt = random.uniform(500_000, 2_500_000)
    elif typology == 'social_engineering':
        amt = random.uniform(200_000, 1_500_000)
    else:
        amt = random.uniform(300_000, 3_000_000)
    return round(amt / 1000) * 1000   # always round thousands


def _velocity(is_fraud: bool, typology: str = None):
    """Return (count_1h, count_24h)."""
    if is_fraud and typology in ('sim_swap', 'account_takeover'):
        c1h  = random.randint(5, 20)
        c24h = random.randint(c1h, c1h + 30)
    elif is_fraud:
        c1h  = random.randint(2, 6)
        c24h = random.randint(c1h, c1h + 10)
    else:
        c1h  = random.randint(1, 3)
        c24h = random.randint(c1h, c1h + 8)
    return c1h, c24h


def generate_transaction(force_fraud: bool = False) -> dict:
    """Return one synthetic transaction dict ready for inference."""
    global _bad_receivers

    now   = datetime.now(timezone.utc)
    hour  = now.hour
    is_night = hour >= 22 or hour <= 5

    # Decide fraud — night triples the base rate
    effective_fraud_rate = BASE_FRAUD_RATE * (3 if is_night else 1)
    is_fraud = force_fraud or (random.random() < effective_fraud_rate)
    typology = random.choices(FRAUD_TYPES, weights=FRAUD_WEIGHTS)[0] if is_fraud else None

    sender   = _phone(MTN_PREFIXES if random.random() < 0.6 else AIRTEL_PREFIXES)
    receiver = _phone()

    # Reuse a known bad receiver occasionally (repeat offender pattern)
    if is_fraud and _bad_receivers and random.random() < 0.35:
        receiver = random.choice(_bad_receivers)
    if is_fraud and receiver not in _bad_receivers and random.random() < 0.6:
        _bad_receivers.append(receiver)
        if len(_bad_receivers) > 50:
            _bad_receivers.pop(0)

    receiver_prev_flagged = receiver in _bad_receivers and not is_fraud and random.random() < 0.3

    amount   = _amount_fraud(typology) if is_fraud else _amount_legit()
    c1h, c24h = _velocity(is_fraud, typology)
    sender_age  = random.randint(1, 30) if is_fraud else random.randint(30, 2000)
    recv_age    = random.randint(1, 20) if is_fraud else random.randint(10, 1000)

    channel   = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
    txn_type  = random.choices(TXN_TYPES, weights=TXN_WEIGHTS)[0]
    is_weekend = now.weekday() >= 5
    deviation  = (amount - 50000) / 50000 if is_fraud else random.uniform(-0.5, 0.5)
    round_amt  = (amount % 1000 == 0)

    return {
        'txn_id':                      _txn_id(),
        'sender':                      sender,
        'receiver':                    receiver,
        'amount_ugx':                  round(amount, 2),
        'txn_type':                    txn_type,
        'hour':                        hour,
        'channel':                     channel,
        'is_weekend':                  int(is_weekend),
        'sender_account_age_days':     sender_age,
        'receiver_account_age_days':   recv_age,
        'is_new_receiver':             int(recv_age < 30),
        'sender_txn_count_1h':         c1h,
        'sender_txn_count_24h':        c24h,
        'amount_deviation':            round(deviation, 4),
        'receiver_previously_flagged': int(receiver_prev_flagged),
        'round_amount':                int(round_amt),
        # Metadata only (not used in model features)
        '_is_fraud_ground_truth':      is_fraud,
        '_typology':                   typology,
        '_timestamp':                  now.isoformat(),
    }
