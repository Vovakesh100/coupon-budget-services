"""Redis implementation of BudgetStore. The budget check and charge run as one Lua script.

Key layout (hash tag {c:<campaign>} keeps every key of a campaign in one Redis Cluster slot):
- {c:<cid>}:meta            hash: total, spent (micro), ends_at (unix seconds)
- {c:<cid>}:coupon:<id>     hash: face_value (micro), redeemed ("0" or "1")
- {c:<cid>}:idem:<key>      string: coupon id, expires after the idempotency TTL
- coupon_index:<id>         string: campaign id (immutable, read before the script)

Amounts are kept in Lua numbers (doubles), so they must stay below 2**53 micro units.
"""

from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis

from coupon_budget.domain.budget import Budget, BudgetExceededError, Campaign
from coupon_budget.domain.coupon import (
    CampaignExpiredError,
    Coupon,
    CouponAlreadyRedeemedError,
)
from coupon_budget.domain.money import Money
from coupon_budget.ports.budget_store import (
    CampaignNotFoundError,
    CouponNotFoundError,
    IdempotencyKeyReusedError,
)

REDEEM_SCRIPT = """
-- KEYS[1]=meta, KEYS[2]=coupon, KEYS[3]=idem
-- ARGV[1]=coupon_id, ARGV[2]=now (unix seconds), ARGV[3]=idempotency TTL (ms)
local seen = redis.call('GET', KEYS[3])
if seen then
  if seen ~= ARGV[1] then return 'reused' end
  return 'replay'
end
if redis.call('EXISTS', KEYS[2]) == 0 then return 'no_coupon' end
local ends_at = tonumber(redis.call('HGET', KEYS[1], 'ends_at'))
if tonumber(ARGV[2]) >= ends_at then return 'expired' end
if redis.call('HGET', KEYS[2], 'redeemed') == '1' then return 'already' end
local total = tonumber(redis.call('HGET', KEYS[1], 'total'))
local spent = tonumber(redis.call('HGET', KEYS[1], 'spent'))
local face = tonumber(redis.call('HGET', KEYS[2], 'face_value'))
if spent + face > total then return 'budget' end
redis.call('HINCRBY', KEYS[1], 'spent', face)
redis.call('HSET', KEYS[2], 'redeemed', '1')
redis.call('SET', KEYS[3], ARGV[1], 'PX', ARGV[3])
return 'ok'
"""


def _meta_key(campaign_id: str) -> str:
    return f"{{c:{campaign_id}}}:meta"


def _coupon_key(campaign_id: str, coupon_id: str) -> str:
    return f"{{c:{campaign_id}}}:coupon:{coupon_id}"


def _idem_key(campaign_id: str, key: str) -> str:
    return f"{{c:{campaign_id}}}:idem:{key}"


def _index_key(coupon_id: str) -> str:
    return f"coupon_index:{coupon_id}"


def _text(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class RedisBudgetStore:
    def __init__(self, redis: Redis, idempotency_ttl_seconds: int) -> None:
        self._redis = redis
        self._idem_ttl_ms = idempotency_ttl_seconds * 1000
        self._redeem = redis.register_script(REDEEM_SCRIPT)

    async def add_campaign(self, campaign: Campaign) -> None:
        await self._redis.hset(
            _meta_key(campaign.id),
            mapping={
                "total": campaign.budget.total.micro,
                "spent": campaign.budget.spent.micro,
                "ends_at": int(campaign.ends_at.timestamp()),
            },
        )

    async def add_coupon(self, coupon: Coupon) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(
                _coupon_key(coupon.campaign_id, coupon.id),
                mapping={
                    "face_value": coupon.face_value.micro,
                    "redeemed": "1" if coupon.redeemed else "0",
                },
            )
            pipe.set(_index_key(coupon.id), coupon.campaign_id)
            await pipe.execute()

    async def get_campaign(self, campaign_id: str) -> Campaign | None:
        raw = await self._redis.hgetall(_meta_key(campaign_id))
        if not raw:
            return None
        values = {_text(k): int(_text(v)) for k, v in raw.items()}
        return Campaign(
            id=campaign_id,
            budget=Budget(Money(values["total"]), Money(values["spent"])),
            ends_at=datetime.fromtimestamp(values["ends_at"], tz=UTC),
        )

    async def get_coupon(self, coupon_id: str) -> Coupon | None:
        campaign_id = await self._redis.get(_index_key(coupon_id))
        if campaign_id is None:
            return None
        cid = _text(campaign_id)
        raw = await self._redis.hgetall(_coupon_key(cid, coupon_id))
        if not raw:
            return None
        values = {_text(k): _text(v) for k, v in raw.items()}
        return Coupon(
            id=coupon_id,
            campaign_id=cid,
            face_value=Money(int(values["face_value"])),
            redeemed=values["redeemed"] == "1",
        )

    async def redeem(self, coupon_id: str, idempotency_key: str, now: datetime) -> Coupon:
        campaign_id_raw = await self._redis.get(_index_key(coupon_id))
        if campaign_id_raw is None:
            raise CouponNotFoundError(coupon_id)
        cid = _text(campaign_id_raw)
        outcome = _text(
            await self._redeem(
                keys=[_meta_key(cid), _coupon_key(cid, coupon_id), _idem_key(cid, idempotency_key)],
                args=[coupon_id, int(now.timestamp()), self._idem_ttl_ms],
            )
        )
        if outcome in ("ok", "replay"):
            coupon = await self.get_coupon(coupon_id)
            if coupon is None:
                raise CouponNotFoundError(coupon_id)
            return coupon
        errors: dict[str, type[Exception]] = {
            "reused": IdempotencyKeyReusedError,
            "no_coupon": CouponNotFoundError,
            "expired": CampaignExpiredError,
            "already": CouponAlreadyRedeemedError,
            "budget": BudgetExceededError,
        }
        if outcome == "no_coupon":
            raise CouponNotFoundError(coupon_id)
        if outcome not in errors:
            raise CampaignNotFoundError(cid)
        raise errors[outcome](coupon_id)
