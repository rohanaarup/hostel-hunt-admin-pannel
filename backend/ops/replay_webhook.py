"""
Replay a Razorpay webhook against STAGING, to prove a repeated delivery changes nothing.

Run it on your own computer. The webhook secret is read from an environment variable and never printed:

    set RAZORPAY_WEBHOOK_SECRET=<the secret from the Razorpay TEST dashboard>      (Windows cmd)
    python ops/replay_webhook.py --url https://<staging host>/api/v1/payments/webhook/ ^
        --order order_XXXX --payment pay_XXXX --amount-rupees 6500 --times 2

It sends one signed `payment.captured` event, `--times` times, with the SAME event id each time. The first
delivery confirms the payment (if it is not confirmed yet); every repeat must answer {"status": "duplicate"}.
It refuses to run against the production host.
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request

PRODUCTION_HOSTS = ('hostel-hunt-backend.onrender.com',)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', required=True, help='full webhook URL of the STAGING service')
    parser.add_argument('--order', required=True, help='Razorpay order id (order_...)')
    parser.add_argument('--payment', required=True, help='Razorpay payment id (pay_...)')
    parser.add_argument('--amount-rupees', required=True, type=float, help='amount of the order in rupees')
    parser.add_argument('--event', default='payment.captured', choices=['payment.captured', 'order.paid', 'payment.failed'])
    parser.add_argument('--event-id', default='evt_replay_test_1', help='the same id is reused for every delivery')
    parser.add_argument('--times', type=int, default=2)
    args = parser.parse_args()

    if any(host in args.url for host in PRODUCTION_HOSTS):
        sys.exit('Refusing to send test events to the production host.')
    secret = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
    if not secret:
        sys.exit('Set the RAZORPAY_WEBHOOK_SECRET environment variable first (the TEST-mode webhook secret).')

    body = json.dumps({
        'event': args.event,
        'payload': {'payment': {'entity': {
            'id': args.payment, 'order_id': args.order, 'amount': int(round(args.amount_rupees * 100)), 'currency': 'INR',
        }}},
    }).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    for n in range(1, args.times + 1):
        request = urllib.request.Request(args.url, data=body, method='POST', headers={
            'Content-Type': 'application/json',
            'X-Razorpay-Signature': signature,
            'X-Razorpay-Event-Id': args.event_id,
        })
        try:
            with urllib.request.urlopen(request, timeout=60) as reply:
                print(f'delivery {n}: HTTP {reply.status} {reply.read().decode()[:200]}')
        except urllib.error.HTTPError as err:
            print(f'delivery {n}: HTTP {err.code} {err.read().decode()[:200]}')


if __name__ == '__main__':
    main()
