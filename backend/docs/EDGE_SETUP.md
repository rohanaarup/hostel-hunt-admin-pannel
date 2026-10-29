# Putting Cloudflare in front of the backend (founder guide)

**Status:** the code side is done and tested (Phase 3). **Nothing in this guide has been done**: it needs a domain, a Cloudflare
account and dashboard clicks that only you can make, so it is on your deferred list (`FOUNDER_DEFERRED.md`). Do it on
**staging first**, check each step, then production.

**Why.** Cloudflare sits between the phones and Render. It (1) answers the public lists from its own cache, so most reads
never reach the server, (2) blocks junk and attacks before they cost anything, (3) hides the real server address, and
(4) gives you a rate rule on sign-in paths that does not depend on the app. The server side is ready for it: cache headers
the edge can obey, an optional shared secret so nobody can skip the edge, and a log field to prove the client address is read
correctly.

**Cloudflare screen names and plan limits change.** Menu names below are from memory of Cloudflare's dashboard and docs;
where a step says "confirm", read the screen or Cloudflare's current docs first. Free-plan limits (how many rate rules,
which WAF rules) must be read on Cloudflare's plans page the day you decide. Claude cannot see your Cloudflare account.

## What you need and what it costs (approve before starting)

| Item | Note |
|---|---|
| A domain name | A yearly fee at a registrar of your choice. Read the price. You said you had no domain on 2026-10-11 (Brevo and Resend notes), so this is new. |
| A Cloudflare account | The free plan is the starting point; read its limits (rate rules, WAF) on the plans page. |
| Render | The custom domain on the production web service. The paid sizes and Key Value in `render.scale.yaml` are separate decisions (`CAPACITY.md`). |

## Names used below (replace with yours)

`example.com` is your domain; the API will be `api.example.com`. The Render address stays `hostel-hunt-backend.onrender.com`
(the **origin**).

## Step 1. Domain and DNS

1. Add the domain to Cloudflare (Add a site) and change the registrar's nameservers to the two Cloudflare gives you.
2. In Render, production web service, Settings, Custom Domains: add `api.example.com`. Render shows the DNS record it expects.
3. In Cloudflare, DNS: create that record (usually a CNAME `api` to `hostel-hunt-backend.onrender.com`). Start with the cloud
   **grey (DNS only)** until Render shows the domain as verified and its certificate as issued (Render's custom-domain docs
   describe verification; confirm whether it works while proxied). Then switch the record to **orange (proxied)**.

**Check:** `https://api.example.com/healthz` answers `{"status": "ok", ...}` while grey, and still does after turning orange.

## Step 2. TLS and basic security

- SSL/TLS, Overview: set the mode to **Full (strict)**. (Render presents a valid certificate for your domain; strict checks
  it. Flexible would send traffic to Render unencrypted: never use it.)
- Edge Certificates: turn on **Always Use HTTPS**; set the minimum TLS version to 1.2.
- Security: turn on the **managed WAF rules** and **Bot Fight Mode** (names vary by plan; confirm). DDoS protection is automatic.
- Do **not** turn on HSTS here until `FOUNDER_CHECKLIST_PROD.md` says HTTPS is proven on this final domain.

**Check:** `https://api.example.com/api/v1/cities/` loads; `http://api.example.com` redirects to https.

## Step 3. Cache rules (public GET answers only)

The server marks which answers may be shared: only the four public reads carry `Cache-Control: public, max-age=N,
s-maxage=N` (30 s for the hostel list, 120 s for cities and localities); **every other answer says
`private, no-store`**. Cloudflare does not cache JSON by default, so one rule is needed to let it keep these four, and it
must obey the server's header rather than invent its own.

Create **one Cache Rule** (Caching, Cache Rules):

- **When:** the path is exactly `/api/v1/hostels/`, or `/api/v1/cities/`, or `/api/v1/hostels/localities/`, or matches
  `/api/v1/cities/*/localities/`, **and** the method is GET, **and** the request has **no `Authorization` header**.
- **Then:** Eligible for cache; Edge TTL: **use the origin's Cache-Control header** (and do not override the browser TTL);
  cache key includes the query string (the default).
- **Everything else stays uncached by default.** Add an explicit **Bypass cache** rule, placed first, for paths starting with
  `/api/v1/stays`, `/api/v1/payments`, `/api/v1/notifications`, `/api/v1/auth`, `/api/v1/bookings`, `/api/v1/dashboard` and
  `/admin`, and for any request carrying an `Authorization` header. These endpoints already answer `private, no-store`; the
  rule is a second lock.
- Cloudflare's expression editor has a function for "header is present"; use the editor's help to write the Authorization
  condition (confirm the exact syntax there).

**Check (two requests in a row from a terminal):**

```
curl -sI "https://api.example.com/api/v1/cities/" | findstr /i "cf-cache-status cache-control"
```

The first shows `cf-cache-status: MISS`, the second `HIT`, and `cache-control` contains `s-maxage=120`. Then
`curl -sI -H "Authorization: Bearer x" https://api.example.com/api/v1/cities/` must **not** say `HIT` and its
`cache-control` must be `private, no-store`.

## Step 4. Rate rules for sign-in paths

The app already limits sign-in itself (a code attempt cap, a per-address throttle, per-record cooldowns). The edge adds a
cheap first line of defence. Create **Rate limiting rules** (Security, WAF, Rate limiting rules) for these real paths
(`apps/owners/urls.py`):

| Paths | Starting limit per address | Action |
|---|---|---|
| `/api/v1/auth/send-otp/`, `/api/v1/auth/resend-otp/`, `/api/v1/auth/forgot-password/` | 20 requests per minute | block for a short time |
| `/api/v1/auth/verify-otp/`, `/api/v1/auth/reset-password/` | 30 per minute | block for a short time |
| `/api/v1/auth/login/`, `/api/v1/auth/register/` | 30 per minute | block for a short time |

These match the app's own limits (`otp_send` 20/min, `otp_verify` 30/min) so the edge never blocks someone the app would
have allowed. **Start in the "log only" action if your plan offers it** and read the matches for a week before blocking
(confirm what your plan allows; free plans limit how many rules you can have: if only one, use the OTP-send rule first).

## Step 5. The Razorpay webhook must never be blocked

Razorpay's server calls `POST /api/v1/payments/webhook/` (`apps/payments/urls.py`). A firewall or bot rule that challenges or
blocks it means paid students stay at "Still Waiting". Create a **WAF custom rule with action Skip** placed first:

- **When:** the path is exactly `/api/v1/payments/webhook/`.
- **Skip:** all managed rules, Bot Fight Mode / super bot rules, rate limiting rules, and security level (the options offered
  in the Skip action).
- The webhook is protected by its signature (`RAZORPAY_WEBHOOK_SECRET`), which the server checks itself. If you also want to
  limit it to Razorpay's addresses, take the list from Razorpay's documentation (do not copy it from memory).

**Check:** after the staging payment test (`PAYMENT_TEST.md`), the Razorpay webhook delivery log shows `200`, and the
Cloudflare Security events list shows no block or challenge on that path.

## Step 6. Lock the origin: the shared secret

Without this, anyone who learns `hostel-hunt-backend.onrender.com` can skip all of the above (and can write the
`X-Forwarded-For` header themselves, which would let them fake their address).

1. Make a long random value (for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`). **Do not paste it
   anywhere but the two places below.**
2. Cloudflare, Rules, Transform Rules, **Modify Request Header**: for all requests to `api.example.com`, **Set static**
   header `X-Edge-Secret` to that value.
3. Render production web service, Environment: `EDGE_SHARED_SECRET` = the same value. Deploy.

The server then refuses any request without the right header with a plain `403`, **except `/healthz` and `/readyz`**, so
Render's own health checks keep working.

**Check:** `curl -s -o NUL -w "%{http_code}" https://hostel-hunt-backend.onrender.com/api/v1/cities/` prints `403` (direct,
no header); `https://api.example.com/api/v1/cities/` prints `200`; `https://hostel-hunt-backend.onrender.com/healthz`
prints `200`. If everything returns 403, the transform rule is missing or the values differ.

**If you lock yourself out:** remove `EDGE_SHARED_SECRET` from Render and redeploy; the server stops checking at once.

## Step 7. Hosts, browsers and the hop count (environment values)

All through Render's environment (names only; values are yours):

| Variable | Set to |
|---|---|
| `ALLOWED_HOSTS` | keep the old host **and add** `api.example.com` (comma-separated). A wrong value makes every call answer 400. |
| `CORS_ALLOWED_ORIGINS` | the origins of the admin site (with `https://`), if a browser site calls the API |
| `CSRF_TRUSTED_ORIGINS` | `https://api.example.com` (for `/admin/` login over HTTPS) |
| `TRUSTED_PROXY_COUNT` | **2** (Cloudflare, then Render) **only after the test below passes**; leave it at 1 until then |

**Why the hop count matters.** The server finds the client's address by counting proxies from the end of the
`X-Forwarded-For` header. With Cloudflare and Render in front there are two, so the real address is the second from the
end. If the count is 1 the server would read **Cloudflare's** address instead, and thousands of phones would all look like one
client and share one 60-a-minute allowance. If the count is too high it reads an address the client wrote. So prove it.

### The two-phone test

You need two phones on **different** networks (for example one on mobile data and one on Wi-Fi, or two different carriers).
Use a request that is **not cached** (so it reaches the server and appears in the log): the readiness URL with a throwaway
query.

1. In Render set `TRUSTED_PROXY_COUNT` to `2` and redeploy (staging first).
2. Phone A opens `https://api.example.com/readyz?probe=a`. Phone B opens `https://api.example.com/readyz?probe=b`.
   Each should show `{"status": "ok"}`.
3. In Render's Logs, find the two request lines for route `readyz`. Read two fields on each (they hold no address, only a
   count and a masked identifier): **`client`** (8 characters, changes daily) and **`xff_hops`**.

| What you see | It means | Do |
|---|---|---|
| `xff_hops` is 2 on both and the two `client` values **differ** | correct | keep `TRUSTED_PROXY_COUNT=2` |
| `xff_hops` is 2 but the two `client` values are the **same** | the count is too low: both read Cloudflare's address | check `TRUSTED_PROXY_COUNT` really is 2 and redeployed |
| `xff_hops` is 1 | Cloudflare is not adding itself, or the request skipped it | check the DNS record is orange and you used the `api.example.com` address |
| `xff_hops` is 3 or more | another proxy is in the chain | tell Claude; the count must equal the real number of proxies |

4. Optional: phone A opens the URL twice, a minute apart. Both lines must show the **same** `client` (Cloudflare may use a
   different edge server each time; that must not change the value).

The `client` value is a keyed hash of the address, rotated every UTC day, cut to 8 characters: it cannot be turned back into
an address, and it is good only for "are these two requests from different clients". `LOG_CLIENT_ID=False` removes it.

## Step 8. Going back

Everything is reversible without touching the data: set the DNS record back to grey (or point the app at the Render address),
set `TRUSTED_PROXY_COUNT` back to 1, remove `EDGE_SHARED_SECRET`. The app's base address change (to `api.example.com`) is an
app release (a later phase), so keep the Render address working during the move.

## Summary of what Claude changed in the repository

| Change | File |
|---|---|
| `s-maxage` on the four public reads; `private, no-store` on everything else | `apps/core/http_cache.py` |
| `EDGE_SHARED_SECRET` guard, health checks exempt | `apps/core/edge.py` |
| masked `client` field in the request log (and `xff_hops` as before) | `apps/core/observability.py` |
| env names listed | `backend/.env.example` |
| tests for all of the above | `apps/core/test_edge.py` |
