#!/usr/bin/env python3
"""
Simulate a cascading infrastructure failure across the distributed stack.


Usage:
    python simulate_failure.py [--api-url http://localhost:8000]


This script simulates:
1. RDBMS Primary outage (150 signals)
2. MCP Host cascade failure due to DB dependency (200 signals)
3. Cache cluster degradation from memory pressure (100 signals)
4. Async queue backlog from failed downstream writes (120 signals)


Each scenario sends signals with a 2-second delay between them to demonstrate
the debouncing logic (100+ signals within 10s → 1 work item per component).
"""


import json
import time
import argparse
import urllib.request
import urllib.error




def send_signals(api_url: str, scenario: dict):
    """Send a batch of signals for a failure scenario."""
    print(f"\n{'=' * 60}")
    print(f"SCENARIO: {scenario['name']}")
    print(f"Component: {scenario['component_id']} ({scenario['component_type']})")
    print(f"Sending {scenario['signal_count']} signals...")
    print(f"{'=' * 60}")


    signals = []
    for i in range(scenario["signal_count"]):
        signals.append(
            {
                "component_id": scenario["component_id"],
                "component_type": scenario["component_type"],
                "error_code": scenario["error_code"],
                "error_message": scenario["error_message"],
                "latency_ms": scenario["latency_ms"],
                "metadata": {"simulation": True, "sequence": i + 1},
            }
        )


    # Send as batch
    payload = json.dumps({"signals": signals}).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url}/signals/batch",
        data=payload,
        headers={"Content-Type": "application/json"},
    )


    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(
                f"  ✓ Sent {result.get('accepted', scenario['signal_count'])} signals"
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ✗ Error {e.code}: {body}")
    except urllib.error.URLError as e:
        print(f"  ✗ Connection failed: {e.reason}")
        print(f"    Make sure the backend is running at {api_url}")
        return False


    return True




def check_incidents(api_url: str):
    """Check created incidents after simulation."""
    print(f"\n{'=' * 60}")
    print("RESULTS: Created Incidents")
    print(f"{'=' * 60}")


    try:
        req = urllib.request.Request(f"{api_url}/incidents?active_only=true")
        with urllib.request.urlopen(req) as resp:
            incidents = json.loads(resp.read())
            for inc in incidents:
                print(f"  [{inc['severity']}] {inc['title']}")
                print(
                    f"       Status: {inc['status']} | Signals: {inc['signal_count']}"
                )
                if inc.get("sla_remaining_seconds"):
                    mins = inc["sla_remaining_seconds"] / 60
                    print(f"       SLA Remaining: {mins:.1f} min")
                print()
    except Exception as e:
        print(f"  Could not fetch incidents: {e}")




def main():
    parser = argparse.ArgumentParser(
        description="Simulate cascading infrastructure failure"
    )
    parser.add_argument(
        "--api-url", default="http://localhost:8000", help="Backend API URL"
    )
    args = parser.parse_args()


    # Load scenarios
    with open("sample_data/cascade_failure.json") as f:
        data = json.load(f)


    print(f"IMS Failure Simulation")
    print(f"Target: {args.api_url}")
    print(f"Scenarios: {len(data['scenarios'])}")


    for scenario in data["scenarios"]:
        success = send_signals(args.api_url, scenario)
        if not success:
            return
        time.sleep(2)  # Pause between scenarios


    # Wait for debouncing to complete
    print("\n⏳ Waiting 12 seconds for debounce processing...")
    time.sleep(12)


    check_incidents(args.api_url)
    print("✓ Simulation complete!")




if __name__ == "__main__":
    main()



