(() => {
  const banner = document.getElementById("login-sync");
  if (!banner) return;
  const message = banner.querySelector("[data-sync-message]");
  const started = Date.now();
  let failures = 0;

  function notice(text) {
    banner.classList.add("login-sync-idle");
    message.textContent = text;
  }

  async function poll() {
    if (Date.now() - started > 120000) {
      notice("La mise à jour prend plus de temps que prévu. Tes candidatures restent accessibles ; consulte les travaux pour suivre la suite.");
      return;
    }
    try {
      const response = await fetch(banner.dataset.statusUrl, {
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
        headers: { Accept: "application/json" },
      });
      if (response.redirected || response.status === 401) {
        banner.hidden = true;
        return;
      }
      if (!response.ok) throw new Error("status unavailable");
      const status = await response.json();
      failures = 0;
      if (!status.pending) {
        if (status.failed) {
          notice("Mise à jour incomplète : réseau ou connecteur indisponible, ou traitement en échec. Tes candidatures restent accessibles. Consulte les travaux pour réessayer.");
        } else {
          banner.hidden = true;
          if (window.location.pathname === banner.dataset.dashboardUrl ||
              window.location.pathname === banner.dataset.metricsUrl) {
            window.location.reload();
          }
        }
        return;
      }
      if (status.queued && Date.now() - started > 30000) {
        notice("Mise à jour en attente. Vérifie que le worker est démarré ; tes candidatures restent accessibles.");
      } else {
        banner.classList.remove("login-sync-idle");
        message.textContent = "Mise à jour de tes candidatures en cours… Tu peux continuer à naviguer.";
      }
    } catch {
      failures += 1;
      if (failures >= 3) {
        notice("Le suivi est momentanément indisponible. Tu peux continuer à consulter tes candidatures et actualiser la page plus tard.");
        return;
      }
    }
    window.setTimeout(poll, 2000);
  }
  poll();
})();
