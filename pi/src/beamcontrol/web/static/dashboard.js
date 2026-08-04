async function refresh(element) {
  if (element.dataset.refreshing) return;
  element.dataset.refreshing = "true";
  try {
    const response = await fetch(element.dataset.refreshUrl, { cache: "no-store" });
    if (!response.ok) return;
    const template = document.createElement("template");
    template.innerHTML = await response.text();
    element.replaceWith(template.content.firstElementChild);
  } finally {
    delete element.dataset.refreshing;
  }
}

setInterval(() => {
  document.querySelectorAll("[data-refresh-url]").forEach(refresh);
}, 2000);
