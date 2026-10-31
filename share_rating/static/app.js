// Card interactions: ask "Rated?" after opening IMDb, hide with ✕.
document.querySelectorAll(".card").forEach((card) => {
  const imdbId = card.dataset.imdbId;
  const error = card.querySelector(".error");

  async function post(path) {
    error.hidden = true;
    try {
      const resp = await fetch(`/${path}/${imdbId}`, { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      card.remove();
    } catch (e) {
      error.textContent = `Could not save: ${e.message}`;
      error.hidden = false;
    }
  }

  // Let the link open IMDb in a new tab, then ask on return.
  card.querySelectorAll("a").forEach((link) =>
    link.addEventListener("click", () => card.classList.add("asking"))
  );
  card.querySelector(".rated").addEventListener("click", () => post("rated"));
  card.querySelector(".not-yet").addEventListener("click", () => card.classList.remove("asking"));
  card.querySelector(".hide").addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    post("hide");
  });
});
