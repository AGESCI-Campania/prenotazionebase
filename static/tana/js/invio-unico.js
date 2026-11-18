// Form con data-invio-unico: il secondo invio (doppio clic mentre il server risponde) si ignora.
// Il pulsante non si disattiva: un pulsante disattivato non invierebbe il suo name/value.
for (const form of document.querySelectorAll("form[data-invio-unico]")) {
  form.addEventListener("submit", (evento) => {
    if (form.dataset.inviato) {
      evento.preventDefault();
      return;
    }
    form.dataset.inviato = "1";
    form.setAttribute("aria-busy", "true");
  });
}
