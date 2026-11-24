"""Measure a cold navigation in Chromium (optional dependency: playwright)."""
import argparse
import json
from statistics import median

from playwright.sync_api import sync_playwright


# Count the first full point draw and the following animation frame. The latter is
# a presentation proxy. The loading overlay must also have been removed.
INSTRUMENT = """
window.proofMapBenchmark = {};
const stats = window.proofMapBenchmark;
new MutationObserver(records => {
  if (records.some(r => [...r.removedNodes].some(n => n.id === "loading")))
    stats.uncovered = performance.now();
}).observe(document, {subtree: true, childList: true});
const draw = WebGL2RenderingContext.prototype.drawElements;
WebGL2RenderingContext.prototype.drawElements = function(...args) {
  if (args[0] === this.POINTS && args[1] > 1000000 && !stats.points) {
    stats.points = args[1];
    requestAnimationFrame(() => stats.frame = performance.now());
  }
  return draw.apply(this, args);
};
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--mbps", type=float, help="throttle download and upload, with 20 ms latency")
    parser.add_argument("--browser", help="path to an existing Chromium executable")
    parser.add_argument("--software", action="store_true", help="render with SwiftShader")
    args = parser.parse_args()
    samples = []
    with sync_playwright() as p:
        flags = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if args.software else []
        browser = p.chromium.launch(executable_path=args.browser, args=flags)
        for _ in range(args.runs):
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            page.add_init_script(INSTRUMENT)
            if args.mbps:
                dev = context.new_cdp_session(page)
                dev.send("Network.enable")
                rate = args.mbps * 1e6 / 8
                dev.send("Network.emulateNetworkConditions", {
                    "offline": False, "downloadThroughput": rate, "uploadThroughput": rate, "latency": 20,
                })
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_function("proofMapBenchmark.frame && proofMapBenchmark.uncovered", timeout=120000)
            result = page.evaluate("""() => ({
              ...proofMapBenchmark,
              bytes: performance.getEntriesByType("resource")
                .filter(e => e.name.startsWith(location.origin + "/"))
                .reduce((n, e) => n + e.encodedBodySize, 0)
            })""")
            result["visible_ms"] = max(result["uncovered"], result["frame"])
            print(json.dumps(result), flush=True)
            samples.append(result["visible_ms"])
            context.close()
        browser.close()
    print(f"Median time to visible map: {median(samples) / 1000:.2f} s")


if __name__ == "__main__":
    main()
