"use strict";

const providerSelect = document.getElementById("account-provider");
if (providerSelect) {
    const passwordInput = document.getElementById("account-password");
    const wasRequired = passwordInput.required;
    providerSelect.addEventListener("change", () => {
        const selected = providerSelect.selectedOptions[0];
        const oauth = selected.dataset.auth === "oauth2";
        document.getElementById("account-auth").value = selected.dataset.auth;
        document.getElementById("oauth-help").hidden = !oauth;
        document.getElementById("password-field").hidden = oauth;
        passwordInput.required = !oauth && wasRequired;
        passwordInput.disabled = oauth;
        passwordInput.value = "";
        if (selected.dataset.host) {
            document.getElementById("account-host").value = selected.dataset.host;
            document.getElementById("account-port").value = selected.dataset.port;
            document.querySelector('input[name="use_ssl"]').checked = true;
        }
    });
    document.getElementById("account-email").addEventListener("change", (event) => {
        const username = document.getElementById("account-username");
        if (!username.value) username.value = event.target.value;
    });
}
