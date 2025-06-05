const textarea = document.getElementById('prompt');

function autoResize() {
  textarea.style.height = 'auto';
  textarea.style.height = textarea.scrollHeight + 'px';
}

window.addEventListener('load', () => {
  const scrollTarget = document.getElementById('scroll_to');
  if (scrollTarget) {
    scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});

document.querySelectorAll('.copy-raw-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const rawMarkdown = btn.getAttribute('data-raw');
    if (!rawMarkdown) return alert("No raw markdown found");

    if (navigator.clipboard) {
      navigator.clipboard.writeText(rawMarkdown).then(() => {
        btn.textContent = "Copied!";
        setTimeout(() => btn.textContent = "Copy raw markdown", 1500);
      }).catch(err => alert("Copy failed: " + err));
    } else {
      // Fallback for older browsers
      const textArea = document.createElement("textarea");
      textArea.value = rawMarkdown;
      textArea.style.position = "fixed";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
        btn.textContent = "Copied!";
        setTimeout(() => btn.textContent = "Copy raw markdown", 1500);
      } catch (err) {
        alert("Fallback copy failed: " + err);
      } finally {
        document.body.removeChild(textArea);
      }
    }
  });
});

