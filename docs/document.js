'use strict';
const selected = new URLSearchParams(location.search).get('doc') || '../README.md';
const article = Array.from(document.querySelectorAll('[data-doc]'))
  .find(element => element.dataset.doc === selected);
if (article) {
  // Only the selected document owns anchor IDs; hidden documents may share headings.
  for (const hiddenArticle of document.querySelectorAll('[data-doc]')) {
    if (hiddenArticle !== article) {
      for (const heading of hiddenArticle.querySelectorAll('[id]')) heading.removeAttribute('id');
    }
  }
  article.hidden = false;
  document.title = `${article.dataset.title} · Bonsai 2 27B`;
  if (location.hash) {
    try {
      document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
    } catch {
      // A malformed fragment does not prevent reading the document.
    }
  }
} else {
  document.getElementById('document-error').hidden = false;
}
