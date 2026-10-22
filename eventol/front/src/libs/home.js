// The templates reuse the React home's styles, in their original cascade order.
import '../components/Hero/index.scss';
import '../components/Logo/index.scss';
import '../components/Navigation/index.scss';
import '../components/UserProfile/index.scss';
import '../components/SignIn/index.scss';
import '../components/Header/index.scss';
import '../components/Search/index.scss';
import '../components/Map/index.scss';
import '../components/Item/index.scss';
import '../components/Slider/index.css';
import '../components/TitleList/index.scss';
import '../containers/Home/index.scss';
import '../views/index.scss';
import './home.scss';

import 'slick-carousel/slick/slick';

import {loadMap} from '../utils/map';
import {SLIDER_BASE_SETTINGS} from '../utils/constants';

const initialize = root => {
  root
    .querySelectorAll('[data-home-slider]:not(.slick-initialized)')
    .forEach(el => {
      $(el).slick({
        ...SLIDER_BASE_SETTINGS,
        prevArrow:
          '<div class="arrow arrow-prev fa fa-chevron-left" role="button" tabindex="0" style="display:block;color:black"></div>',
        nextArrow:
          '<div class="arrow arrow-next fa fa-chevron-right" role="button" tabindex="0" style="display:block;color:black"></div>',
      });
      el.querySelectorAll('[data-home-map]').forEach(map => {
        // Missing or invalid locations were blank cards in the original home.
        if (map.dataset.place) loadMap(map.dataset.place, map.id);
      });
    });
};

const cleanup = root => {
  root
    .querySelectorAll('.slick-initialized')
    .forEach(el => $(el).slick('unslick'));
};

initialize(document);
document.body.addEventListener('htmx:beforeSwap', event => {
  if (event.detail.shouldSwap) cleanup(event.detail.target);
});
document.body.addEventListener('htmx:afterSwap', event => {
  initialize(event.detail.target);
});

document.getElementById('search').addEventListener('submit', event => {
  if (!document.getElementById('search-input').value) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
});

document.addEventListener('click', event => {
  const toggle = event.target.closest('[data-menu-toggle]');
  if (toggle) {
    const links = document.querySelector('.narrow-links');
    const expanded = links.style.display !== 'block';
    links.style.display = expanded ? 'block' : 'none';
    toggle.setAttribute('aria-expanded', String(expanded));
  }
  if (event.target.closest('[data-search-focus]')) {
    document.getElementById('search-input').focus();
  }
  const language = event.target.closest('[data-language]');
  if (language) {
    event.preventDefault();
    const form = document.getElementById('home-language');
    form.elements.language.value = language.dataset.language;
    form.submit();
  }
  const link = event.target.closest('[data-event-url]');
  if (link) {
    event.preventDefault();
    window.location.href = link.dataset.eventUrl;
  }
});

document.addEventListener('keydown', event => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const target = event.target.closest('[data-event-url], .arrow');
  if (target) {
    event.preventDefault();
    target.click();
  }
});
