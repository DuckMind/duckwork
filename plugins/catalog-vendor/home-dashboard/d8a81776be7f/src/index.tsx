// Entry point: register the Home dashboard component with the Duckwork host.
import HomePage from "./home/HomePage";
import "./home/home.css";

const registry = window.__DUCKWORK_PLUGINS__;
if (registry) {
  registry.register("home-dashboard", HomePage);
} else {
  // eslint-disable-next-line no-console
  console.error("[home-dashboard] __DUCKWORK_PLUGINS__ registry not found");
}
