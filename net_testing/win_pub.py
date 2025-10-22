import argparse
import json
import os
import time
from datetime import datetime, timezone
import zmq

def wait_for_subscriber(pub_sock, timeout_s: float) -> bool:
    """Wait until the bound PUB socket accepts at least one TCP connection."""
    if timeout_s <= 0:
        return False
    mon_addr = "inproc://pub_mon"
    pub_sock.monitor(mon_addr, zmq.EVENT_ACCEPTED)
    mon = pub_sock.get_monitor_socket()
    mon.RCVTIMEO = int(timeout_s * 1000)
    ok = False
    try:
        while True:
            try:
                evt = mon.recv_multipart()
            except zmq.Again:
                break
            if not evt:
                continue
            event_id = int.from_bytes(evt[0][:2], "little")
            if event_id == zmq.EVENT_ACCEPTED:
                ok = True
                break
    finally:
        mon.close(0)
        pub_sock.disable_monitor()
    return ok

def main():
    ap = argparse.ArgumentParser(description="Windows ZMQ PUB (binds; WSL2 NAT-friendly)")
    ap.add_argument("--port", type=int, default=55556, help="Port to bind (default: 55556)")
    ap.add_argument("--bind", default="0.0.0.0", help="Bind IP (default: 0.0.0.0)")
    ap.add_argument("--count", type=int, default=1000, help="Messages to publish")
    ap.add_argument("--rate", type=float, default=15.0, help="Msgs/sec (0 = max)")
    ap.add_argument("--payload", type=int, default=0, help="Payload bytes per message")
    ap.add_argument("--topic", default="demo", help="Topic string")
    ap.add_argument("--wait", type=float, default=2.0, help="Wait up to N seconds for a subscriber")
    args = ap.parse_args()

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    pub.setsockopt(zmq.LINGER, 0)
    pub.setsockopt(zmq.TCP_KEEPALIVE, 1)

    endpoint = f"tcp://{args.bind}:{args.port}"
    pub.bind(endpoint)
    print(f"[PUB] Bound at {endpoint}")

    # Reduce early drops: wait for TCP accept, then small grace for SUBSCRIBE to apply
    if wait_for_subscriber(pub, args.wait):
        print("[PUB] Subscriber connected (TCP). Giving a short grace period...")
        time.sleep(0.2)
    else:
        print("[PUB] No subscriber detected within timeout; publishing anyway (early msgs may be dropped).")

    payload = os.urandom(args.payload) if args.payload > 0 else b""
    interval = 1.0 / args.rate if args.rate > 0 else 0.0
    next_send = time.perf_counter()

    t0 = time.perf_counter()
    try:
        for i in range(args.count):
            header = {
                "seq": i,
                "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "payload_bytes": len(payload),
            }
            frames = [
                args.topic.encode("utf-8"),
                json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n" + payload,
            ]
            pub.send_multipart(frames, copy=False)

            if interval > 0:
                next_send += interval
                delay = next_send - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)

            if (i + 1) % 100 == 0:
                sent = i + 1
                rate = sent / (time.perf_counter() - t0)
                print(f"[PUB] sent {sent}/{args.count} ~{rate:,.0f} msg/s")
    except KeyboardInterrupt:
        print("\n[PUB] Ctrl+C received; stopping...")
    finally:
        pub.close(0)
        ctx.term()
        print("[PUB] Done.")

if __name__ == "__main__":
    main()
