const header = document.querySelector('[data-header]');
const updateHeader = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 8);
};
window.addEventListener('scroll', updateHeader, { passive: true });
updateHeader();

const screenshotSlides = [
  {
    src: 'assets/screenshots/player-section-selection.png',
    alt: 'ClipTap selected section controls inside the YouTube player',
  },
  {
    src: 'assets/screenshots/playlist-page-download.png',
    alt: 'ClipTap playlist page download button',
  },
  {
    src: 'assets/screenshots/channel-download-menu.png',
    alt: 'ClipTap channel download scope menu',
  },
  {
    src: 'assets/screenshots/helper-dashboard.png',
    alt: 'ClipTap Helper dashboard',
  },
  {
    src: 'assets/screenshots/helper-active-download.png',
    alt: 'ClipTap Helper active download queue',
  },
];

const mod = (value, size) => ((value % size) + size) % size;

document.querySelectorAll('[data-screenshot-carousel]').forEach((carousel) => {
  const slots = {
    prev: carousel.querySelector('[data-carousel-slot="prev"]'),
    current: carousel.querySelector('[data-carousel-slot="current"]'),
    next: carousel.querySelector('[data-carousel-slot="next"]'),
  };
  const dots = Array.from(document.querySelectorAll('[data-carousel-dots] button'));
  let currentIndex = 0;

  const setImage = (image, slide) => {
    if (!image || !slide) return;
    image.src = slide.src;
    image.alt = slide.alt;
  };

  const renderCarousel = () => {
    const previousIndex = mod(currentIndex - 1, screenshotSlides.length);
    const nextIndex = mod(currentIndex + 1, screenshotSlides.length);
    setImage(slots.prev, screenshotSlides[previousIndex]);
    setImage(slots.current, screenshotSlides[currentIndex]);
    setImage(slots.next, screenshotSlides[nextIndex]);
    dots.forEach((dot, index) => {
      const isActive = index === currentIndex;
      dot.classList.toggle('active', isActive);
      dot.setAttribute('aria-current', isActive ? 'true' : 'false');
    });
  };

  carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => {
    currentIndex = mod(currentIndex - 1, screenshotSlides.length);
    renderCarousel();
  });

  carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => {
    currentIndex = mod(currentIndex + 1, screenshotSlides.length);
    renderCarousel();
  });

  dots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      currentIndex = index;
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
