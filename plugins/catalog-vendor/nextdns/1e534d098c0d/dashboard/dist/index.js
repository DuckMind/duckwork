/**
 * NextDNS dashboard tab.
 *
 * Plain IIFE, no build step. Uses window.__DUCKWORK_PLUGIN_SDK__ for React and
 * hooks, and talks to the plugin backend at /api/plugins/nextdns/.
 */
(function () {
  "use strict";

  var SDK = window.__DUCKWORK_PLUGIN_SDK__ || {};
  var React = SDK.React;
  if (!React) {
    console.error("[nextdns] Duckwork plugin SDK not available");
    return;
  }
  var h = React.createElement;
  var hooks = SDK.hooks || SDK;
  var useState = hooks.useState;
  var useEffect = hooks.useEffect;
  var useCallback = hooks.useCallback;

  var BASE = "/api/plugins/nextdns";

  function api(path, options) {
    if (typeof SDK.fetchJSON === "function") return SDK.fetchJSON(BASE + path, options);
    var fetcher = typeof SDK.authedFetch === "function" ? SDK.authedFetch : window.fetch;
    return fetcher(BASE + path, options).then(function (r) { return r.json(); });
  }

  var S = {
    page: { padding: "24px", maxWidth: "820px", margin: "0 auto" },
    h1: { fontSize: "20px", fontWeight: 600, marginBottom: "4px" },
    sub: { fontSize: "13px", opacity: 0.7, marginBottom: "20px" },
    card: { border: "1px solid rgba(128,128,128,0.25)", borderRadius: "10px",
            padding: "16px", marginBottom: "16px" },
    cardTitle: { fontSize: "15px", fontWeight: 600, marginBottom: "2px" },
    cardHint: { fontSize: "12px", opacity: 0.65, marginBottom: "14px" },
    label: { fontSize: "13px", marginBottom: "4px" },
    note: { fontSize: "11px", opacity: 0.6, marginTop: "4px" },
    input: { width: "100%", padding: "6px 8px", borderRadius: "6px",
             border: "1px solid rgba(128,128,128,0.35)", background: "transparent",
             color: "inherit", fontSize: "13px", fontFamily: "ui-monospace, monospace" },
    badge: { fontSize: "10px", padding: "1px 6px", borderRadius: "999px",
             border: "1px solid rgba(128,128,128,0.4)", opacity: 0.8, marginLeft: "8px" },
    btn: { padding: "7px 14px", borderRadius: "7px", fontSize: "13px", cursor: "pointer",
           border: "1px solid rgba(128,128,128,0.35)", background: "transparent",
           color: "inherit", marginRight: "8px" },
    status: { fontSize: "12px", marginLeft: "4px", opacity: 0.85 },
    tableRow: { display: "flex", gap: "12px", fontSize: "12px", padding: "3px 0",
                fontFamily: "ui-monospace, monospace" },
    a: { color: "inherit", textDecoration: "underline", opacity: 0.85 }
  };

  function Source(props) {
    if (!props.from || props.from === "settings") return null;
    return h("span", { style: S.badge }, props.from === "env" ? "from env" : "not set");
  }

  function App() {
    var a = useState(null); var st = a[0]; var setSt = a[1];
    var b = useState({}); var src = b[0]; var setSrc = b[1];
    var c = useState(""); var key = c[0]; var setKey = c[1];
    var d = useState(""); var profile = d[0]; var setProfile = d[1];
    var e = useState([]); var profiles = e[0]; var setProfiles = e[1];
    var f = useState(""); var msg = f[0]; var setMsg = f[1];
    var g = useState(null); var check = g[0]; var setCheck = g[1];
    var i = useState([]); var recent = i[0]; var setRecent = i[1];
    var j = useState(false); var busy = j[0]; var setBusy = j[1];

    var load = useCallback(function () {
      api("/settings").then(function (r) {
        if (r && r.ok) {
          setSt(r.settings); setSrc(r.sources || {});
          setProfile(r.settings.profile_id || "");
        } else setMsg((r && r.error) || "failed to load settings");
      }).catch(function (err) { setMsg(String(err)); });
    }, []);

    useEffect(function () { load(); }, [load]);

    function save(then) {
      setBusy(true); setMsg("");
      var patch = { profile_id: profile };
      // Only send the key when the field has been typed into, so saving
      // other changes never clears a stored key.
      if (key) patch.api_key = key;
      api("/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch)
      }).then(function (r) {
        setBusy(false);
        if (r && r.ok) {
          setSt(r.settings); setSrc(r.sources || {}); setKey("");
          setMsg("Saved.");
          if (then) then();
        } else setMsg((r && r.error) || "save failed");
      }).catch(function (err) { setBusy(false); setMsg(String(err)); });
    }

    function loadProfiles() {
      setMsg("");
      api("/profiles").then(function (r) {
        if (r && r.ok) {
          setProfiles(r.profiles || []);
          if (!r.profiles || !r.profiles.length) setMsg("No profiles returned for this key.");
        } else setMsg((r && r.error) || "could not list profiles");
      }).catch(function (err) { setMsg(String(err)); });
    }

    function testIt() {
      setCheck(null); setMsg("");
      api("/test").then(function (r) {
        setCheck(r);
        if (r && r.ok) {
          api("/recent").then(function (x) { if (x && x.ok) setRecent(x.logs || []); })
            .catch(function () {});
        }
      }).catch(function (err) { setMsg(String(err)); });
    }

    if (!st) {
      return h("div", { style: S.page }, h("div", { style: S.sub }, msg || "Loading..."));
    }

    return h("div", { style: S.page },
      h("div", { style: S.h1 }, "NextDNS"),
      h("div", { style: S.sub },
        "API credentials and profile for DNS query triage. Blank fields fall back to environment variables."),

      h("div", { style: S.card },
        h("div", { style: S.cardTitle }, "Credentials"),
        h("div", { style: S.cardHint },
          "Create a key at the bottom of your account page: ",
          h("a", { style: S.a, href: "https://my.nextdns.io/account", target: "_blank",
                   rel: "noreferrer" }, "my.nextdns.io/account")),

        h("div", { style: { marginBottom: "12px" } },
          h("div", { style: S.label }, "API key",
            h("span", { style: S.badge },
              st.api_key_set ? "stored" : "not set"),
            h(Source, { from: st.api_key_set ? src.api_key : null })),
          h("input", {
            type: "password", value: key, style: S.input,
            placeholder: st.api_key_set ? "stored - type to replace" : "paste your API key",
            onChange: function (ev) { setKey(ev.target.value); }
          }),
          h("div", { style: S.note },
            "Never sent back to this page once saved; only whether one exists.")),

        h("div", null,
          h("div", { style: S.label }, "Profile ID", h(Source, { from: src.profile_id })),
          h("input", {
            type: "text", value: profile, style: S.input,
            placeholder: "the path segment of https://dns.nextdns.io/<id>",
            onChange: function (ev) { setProfile(ev.target.value); }
          }),
          h("div", { style: S.note },
            "Also the id shown top-left at my.nextdns.io, or use List profiles below.")),

        profiles.length ? h("div", { style: { marginTop: "12px" } },
          h("div", { style: S.label }, "Profiles on this key"),
          profiles.map(function (p) {
            return h("div", { key: p.id, style: { padding: "3px 0" } },
              h("button", {
                style: S.btn,
                onClick: function () { setProfile(p.id); }
              }, p.id), h("span", { style: S.status }, p.name));
          })) : null,

        h("div", { style: { marginTop: "14px" } },
          h("button", { style: S.btn, disabled: busy,
                        onClick: function () { save(null); } }, busy ? "Saving..." : "Save"),
          h("button", { style: S.btn, onClick: function () { save(loadProfiles); } },
            "Save and list profiles"),
          h("button", { style: S.btn, onClick: testIt }, "Test connection"),
          msg ? h("span", { style: S.status }, msg) : null)),

      check ? h("div", { style: S.card },
        h("div", { style: S.cardTitle }, "Connection"),
        check.ok
          ? h("div", null,
              h("div", { style: { fontSize: "13px" } },
                (check.profile.name || "?") + "  |  logging " +
                (check.profile.logging_enabled ? "enabled" : "DISABLED") +
                "  |  retention " + (check.profile.retention_days || "?") + " days" +
                "  |  region " + (check.profile.log_location || "?")),
              check.profile.logging_enabled ? null : h("div", { style: S.note },
                "Logging is off for this profile, so the log tools will return nothing."))
          : h("div", { style: { fontSize: "13px" } }, "Failed: " + (check.error || "unknown"))) : null,

      recent.length ? h("div", { style: S.card },
        h("div", { style: S.cardTitle }, "Recent blocks"),
        h("div", { style: S.cardHint }, "Confirms data is flowing."),
        recent.map(function (r, n) {
          return h("div", { key: n, style: S.tableRow },
            h("span", { style: { opacity: 0.6, width: "70px" } },
              (r.timestamp || "").slice(11, 19)),
            h("span", { style: { flex: 1 } }, r.domain),
            h("span", { style: { opacity: 0.7 } }, (r.reasons || []).join(", ")));
        })) : null);
  }

  if (window.__DUCKWORK_PLUGINS__ && typeof window.__DUCKWORK_PLUGINS__.register === "function") {
    window.__DUCKWORK_PLUGINS__.register("nextdns", App);
  } else {
    console.error("[nextdns] window.__DUCKWORK_PLUGINS__.register unavailable");
  }
})();
