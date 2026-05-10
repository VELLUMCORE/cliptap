const header = document.querySelector('[data-header]');
const onScroll = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 10);
};
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

document.querySelectorAll('img[data-placeholder]').forEach((image) => {
  image.addEventListener('error', () => {
    const fallback = document.createElement('div');
    fallback.className = 'image-fallback';
    fallback.textContent = image.getAttribute('alt') || 'Screenshot placeholder';
    image.replaceWith(fallback);
  }, { once: true });
});
