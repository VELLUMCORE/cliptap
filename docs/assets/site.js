const header = document.querySelector('[data-header]');
const updateHeader = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 8);
};
window.addEventListener('scroll', updateHeader, { passive: true });
updateHeader();

document.querySelectorAll('[data-screenshot-carousel]').forEach((carousel) => {
  const track = carousel.querySelector('[data-carousel-track]');
  const slides = Array.from(track?.children || []);
  const dotsWrap = carousel.parentElement?.querySelector('[data-carousel-dots]');
  if (!track || slides.length === 0) return;

  let currentIndex = 0;
  let visibleCount = 1;
  let maxIndex = 0;
  let dots = [];

  const getVisibleCount = () => {
    const viewport = carousel.querySelector('.screenshot-viewport');
    const rawValue = viewport ? getComputedStyle(viewport).getPropertyValue('--visible-shots') : '1';
    const parsed = Number.parseInt(rawValue, 10);
    return Number.isFinite(parsed) && parsed > 0 ? Math.min(parsed, slides.length) : 1;
  };

  const buildDots = () => {
    if (!dotsWrap) return;
    dotsWrap.textContent = '';
    dots = Array.from({ length: maxIndex + 1 }, (_, index) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.setAttribute('aria-label', `Show screenshots ${index + 1} to ${Math.min(index + visibleCount, slides.length)}`);
      dot.addEventListener('click', () => {
        currentIndex = index;
        renderCarousel();
      });
      dotsWrap.appendChild(dot);
      return dot;
    });
  };

  const renderCarousel = () => {
    currentIndex = Math.max(0, Math.min(currentIndex, maxIndex));
    const offset = slides[currentIndex]?.offsetLeft || 0;
    track.style.transform = `translateX(-${offset}px)`;
    dots.forEach((dot, index) => {
      const isActive = index === currentIndex;
      dot.classList.toggle('active', isActive);
      dot.setAttribute('aria-current', isActive ? 'true' : 'false');
    });
  };

  const refreshCarousel = () => {
    const nextVisibleCount = getVisibleCount();
    const nextMaxIndex = Math.max(0, slides.length - nextVisibleCount);
    const shouldRebuildDots = nextVisibleCount !== visibleCount || nextMaxIndex !== maxIndex || dots.length === 0;
    visibleCount = nextVisibleCount;
    maxIndex = nextMaxIndex;
    currentIndex = Math.min(currentIndex, maxIndex);
    if (shouldRebuildDots) buildDots();
    renderCarousel();
  };

  carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => {
    currentIndex = currentIndex <= 0 ? maxIndex : currentIndex - 1;
    renderCarousel();
  });

  carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => {
    currentIndex = currentIndex >= maxIndex ? 0 : currentIndex + 1;
    renderCarousel();
  });

  window.addEventListener('resize', refreshCarousel, { passive: true });
  refreshCarousel();
});

document.querySelectorAll('img[data-placeholder]').forEach((image) => {
  image.addEventListener('error', () => {
    const fallback = document.createElement('div');
    fallback.className = 'image-fallback';
    fallback.textContent = image.getAttribute('alt') || 'Screenshot placeholder';
    image.replaceWith(fallback);
  }, { once: true });
});
