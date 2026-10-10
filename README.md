# Lottevo Python

A thin client for the [Lottevo](https://lottevo.com) lottery data API: results, jackpots, schedules,
prize breakdowns and statistics for lotteries worldwide. Standard library only; Python 3.8+.

```bash
pip install lottevo
```

## First call

```python
from lottevo import Client

lottevo = Client("lv_…")  # or set LOTTEVO_API_KEY and pass nothing

account = lottevo.account.get()                              # the smoke test: plan, scopes, quota
draws = lottevo.lotteries.draws("EU-002", {"per_page": 5})   # EuroJackpot's latest results

for draw in draws["data"]:
    print(draw["drawn_at"], *draw["numbers"])
```

Every operation of the API is a method on a resource — `lottevo.lotteries`, `.draws`, `.webhooks`,
`.countries` … — and returns the decoded JSON. Path parameters come first, then the query (or, for
`create`/`update`, the JSON body):

```python
lottevo.draws.list({"filter": {"lottery": ["EU-002", "RO-001"], "from": "2026-01-01"}, "include": "prizes"})
lottevo.lotteries.check("EU-002", {"numbers": "4,7,12,31,44", "bonus": "8,11"})
```

## Pagination

Listings are cursor-paginated. `paginate()` walks every page from the one you give it:

```python
for lottery in lottevo.paginate(lottevo.lotteries.list()):
    print(lottery["code"])
```

## Errors

A refused call raises `LottevoError`. Branch on `code`, not on the message:

```python
from lottevo import LottevoError

try:
    lottevo.lotteries.draws("US-001")
except LottevoError as error:
    if error.code == "lottery_not_entitled":
        ...  # not in your plan
```

`error.status`, `error.request_id` and `error.retry_after` are there too; `lottevo.last_headers` holds
the last answer's headers, including `x-quota-remaining`.

## Options

```python
Client(api_key, locale="ro", timeout=30)
```

`locale` is sent as `Accept-Language`: game names, schedules and error messages come back in it.

Full reference: <https://lottevo.com/docs/reference>.
