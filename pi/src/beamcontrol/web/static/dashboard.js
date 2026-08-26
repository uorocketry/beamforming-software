const events = new EventSource("/events");

events.addEventListener("update", (event) => {
  const update = JSON.parse(event.data);
  const element = document.getElementById(update.id);
  if (!element) return;

  if ("text" in update && element.textContent !== update.text) {
    element.textContent = update.text;
  }
  if ("className" in update && element.className !== update.className) {
    element.className = update.className;
  }
  if ("hidden" in update && element.hidden !== update.hidden) {
    element.hidden = update.hidden;
  }
  if ("html" in update && element.innerHTML.trim() !== update.html.trim()) {
    element.innerHTML = update.html;
  }
});
