const header = document.querySelector('[data-header]');
const updateHeader = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 8);
};
window.addEventListener('scroll', updateHeader, { passive: true });
updateHeader();

document.querySelectorAll('[data-screenshot-carousel]').forEach((carousel) => {
  const track = carousel.querySelector('[data-carousel-track]');
  const slides = Array.from(track?.children || []);
  const dots = Array.from(document.querySelectorAll('[data-carousel-dots] button'));
  if (!track || slides.length === 0) return;

  const mod = (value, size) => ((value % size) + size) % size;
  let currentIndex = 0;

  const renderCarousel = () => {
    track.style.transform = `translateX(-${currentIndex * 100}%)`;
    dots.forEach((dot, index) => {
      const isActive = index === currentIndex;
      dot.classList.toggle('active', isActive);
      dot.setAttribute('aria-current', isActive ? 'true' : 'false');
    });
  };

  carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => {
    currentIndex = mod(currentIndex - 1, slides.length);
    renderCarousel();
  });

  carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => {
    currentIndex = mod(currentIndex + 1, slides.length);
    renderCarousel();
  });

  dots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      currentIndex = mod(index, slides.length);
      renderCarousel();
    });
  });

  renderCarousel();
});

document.querySelectorAll('img[data-placeholder]').forEach((image) => {
  image.addEventListener('error', () => {
    const fallback = document.createElement('div');
    fallback.className = 'image-fallback';
    fallback.textContent = image.getAttribute('alt') || 'Screenshot placeholder';
    image.replaceWith(fallback);
  }, { once: true });
});
