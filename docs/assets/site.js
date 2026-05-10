const header = document.querySelector('[data-header]');
const updateHeader = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 8);
};
window.addEventListener('scroll', updateHeader, { passive: true });
updateHeader();

document.querySelectorAll('img[data-placeholder]').forEach((image) => {
  image.addEventListener('error', () => {
    const fallback = document.createElement('div');
    fallback.className = 'image-fallback';
    fallback.textContent = image.getAttribute('alt') || 'Screenshot placeholder';
    image.replaceWith(fallback);
  }, { once: true });
});
