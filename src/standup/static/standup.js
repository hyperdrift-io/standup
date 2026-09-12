/* Native browser enhancements. The server and real SSE events own the state. */
(() => {
  // Native disclosure is the fallback; hover and focus let people follow the route.
  document.querySelectorAll('[data-route] li details').forEach(station => {
    const summary = station.querySelector('summary');
    let pinned = false;
    let hovered = false;
    station.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse') return;
      hovered = true;
      station.open = true;
    });
    station.addEventListener('pointerleave', () => {
      hovered = false;
      if (!pinned && !station.contains(document.activeElement)) station.open = false;
    });
    station.addEventListener('focusin', () => { station.open = true; });
    station.addEventListener('focusout', event => {
      if (!station.contains(event.relatedTarget) && !pinned && !hovered) station.open = false;
    });
    summary.addEventListener('click', event => {
      event.preventDefault();
      pinned = !pinned;
      station.open = pinned;
    });
    station.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;
      pinned = false;
      summary.focus();
      station.open = false;
      event.stopPropagation();
    });
  });
  const article = document.querySelector('article[data-events]');
  if (!article) return;
  const status = article.querySelector('[role="status"]');
  const retry = article.querySelector('[data-retry]');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let finished = false;
  let source;

  function fail(message, reason) {
    if (finished) return;
    finished = true;
    source?.close();
    article.dataset.state = 'failed';
    status.textContent = message;
    retry.hidden = false;
    window.posthog?.capture('standup_failed', { reason });
  }

  if (!window.EventSource) {
    fail('This browser cannot show live progress. You can still read your brief.', 'events_unavailable');
    retry.querySelector('a').href = `${location.pathname}?wait=1`;
    retry.querySelector('a').textContent = 'Read my brief';
    return;
  }
  source = new EventSource(article.dataset.events);
  source.addEventListener('progress', event => {
    const li = document.createElement('li');
    li.textContent = event.data;
    article.querySelector('ul').append(li);
    if (article.querySelectorAll('li').length === 1) status.textContent = 'Reading your public projects…';
  });
  source.addEventListener('done', event => {
    if (finished) return;
    finished = true;
    source.close();
    const restoreFocus = article.contains(document.activeElement);
    const update = () => {
      const template = document.createElement('template');
      template.innerHTML = event.data;
      const result = template.content.querySelector('article[data-state="done"]');
      if (!result) {
        finished = false;
        fail('The brief could not be displayed. Please try again.', 'invalid_result');
        return;
      }
      article.replaceWith(result);
      if (restoreFocus) result.querySelector('h1').focus({ preventScroll: true });
      const announcement = document.createElement('p');
      announcement.setAttribute('role', 'status');
      result.append(announcement);
      requestAnimationFrame(() => { announcement.textContent = 'Your brief is ready.'; });
      window.posthog?.capture('standup_rendered', {
        handle_length: Number(article.dataset.hl), items: Number(result.dataset.items),
        seconds: Number(result.dataset.seconds), cached: false,
      });
    };
    if (document.startViewTransition && !reducedMotion.matches) {
      const transition = document.startViewTransition(update);
      transition.ready.catch(() => {});
      transition.finished.catch(() => {});
    } else update();
  });
  source.addEventListener('failed', event => fail(event.data, 'run_failed'));
  source.onerror = () => fail('The connection paused. Try again to reconnect to your reading.', 'connection_lost');
  window.addEventListener('pagehide', () => source.close(), { once: true });
  window.addEventListener('pageshow', event => {
    if (event.persisted && !finished) location.reload();
  });
})();
