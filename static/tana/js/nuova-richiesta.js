// Passo 2 della nuova richiesta: mostra solo i campi del tipo di soggiorno scelto e aggiorna il
// preventivo in tempo reale (frammento HTML calcolato dal server con le stesse regole dell'invio).
const form = document.getElementById("passo-soggiorno");
const riquadro = document.getElementById("preventivo");

const CAMPI = {
  TENDE: ["partenza", "persone_tende", "ospiti_data", "ospiti_persone"],
  ACC: ["partenza", "persone_acc", "ospiti_data", "ospiti_persone", "esclusiva_richiesta"],
  CONGIUNTA: ["partenza", "persone_acc", "persone_tende", "ospiti_data", "ospiti_persone"],
  BIVACCO: ["area_bivacco", "persone_acc", "persone_tende"],
  USCITA: ["tipo_uscita", "persone_uscita"],
};
const VARIABILI = new Set(Object.values(CAMPI).flat());

function tipo() {
  return form.querySelector('input[name="tipo"]:checked')?.value;
}

function aggiornaCampi() {
  const visibili = new Set(CAMPI[tipo()] || []);
  if (tipo() === "BIVACCO") {
    const area = form.querySelector('input[name="area_bivacco"]:checked')?.value;
    visibili.delete(area === "TENDE" ? "persone_acc" : "persone_tende");
  }
  for (const campo of form.querySelectorAll("[data-campo]")) {
    const nome = campo.dataset.campo;
    if (VARIABILI.has(nome)) campo.hidden = !visibili.has(nome);
  }
}

let timer;
function aggiornaPreventivo() {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const risposta = await fetch(form.dataset.anteprima, { method: "POST", body: new FormData(form) });
    if (risposta.ok) riquadro.innerHTML = await risposta.text();
  }, 400);
}

form.addEventListener("change", () => {
  aggiornaCampi();
  aggiornaPreventivo();
});
form.addEventListener("input", aggiornaPreventivo);
aggiornaCampi();
aggiornaPreventivo();
