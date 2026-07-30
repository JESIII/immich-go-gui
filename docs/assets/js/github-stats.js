// Client-side dynamic GitHub repository statistics fetcher (stars & forks)
(function () {
  const REPO = "shitan198u/immich-go-gui";
  const CACHE_KEY = "igg_gh_stats_cache";
  const CACHE_TTL_MS = 60 * 1000; // 1 minute cache TTL

  function updateDOM(stars, forks) {
    if (stars === undefined || stars === null) return;

    // 1. Check if star fact elements already exist in the DOM
    const starEls = document.querySelectorAll(".md-source__fact--stars, [data-md-component='source'] .md-source__fact--stars");
    const forkEls = document.querySelectorAll(".md-source__fact--forks, [data-md-component='source'] .md-source__fact--forks");

    if (starEls.length > 0) {
      starEls.forEach(function (el) {
        el.textContent = stars.toLocaleString();
      });
      forkEls.forEach(function (el) {
        if (forks !== undefined && forks !== null) {
          el.textContent = forks.toLocaleString();
        }
      });
      return;
    }

    // 2. If no facts container exists, dynamically create & append facts inside .md-source
    const sources = document.querySelectorAll(".md-source, [data-md-component='source']");
    sources.forEach(function (source) {
      const repoDiv = source.querySelector(".md-source__repository");
      if (!repoDiv) return;

      let factsUl = repoDiv.querySelector(".md-source__facts");
      if (!factsUl) {
        factsUl = document.createElement("ul");
        factsUl.className = "md-source__facts";

        const starLi = document.createElement("li");
        starLi.className = "md-source__fact md-source__fact--stars";
        starLi.textContent = stars.toLocaleString();
        factsUl.appendChild(starLi);

        if (forks !== undefined && forks !== null) {
          const forkLi = document.createElement("li");
          forkLi.className = "md-source__fact md-source__fact--forks";
          forkLi.textContent = forks.toLocaleString();
          factsUl.appendChild(forkLi);
        }

        repoDiv.appendChild(factsUl);
      } else {
        const sLi = factsUl.querySelector(".md-source__fact--stars");
        if (sLi) sLi.textContent = stars.toLocaleString();
        const fLi = factsUl.querySelector(".md-source__fact--forks");
        if (fLi && forks !== undefined && forks !== null) fLi.textContent = forks.toLocaleString();
      }
    });
  }

  function fetchStats() {
    // Detect page reload/refresh to bypass cache
    let isReload = false;
    try {
      if (window.performance && window.performance.getEntriesByType) {
        const navEntries = window.performance.getEntriesByType("navigation");
        if (navEntries.length > 0 && navEntries[0].type === "reload") {
          isReload = true;
        }
      }
    } catch (e) {}

    if (!isReload) {
      try {
        const cached = sessionStorage.getItem(CACHE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Date.now() - parsed.timestamp < CACHE_TTL_MS) {
            updateDOM(parsed.stars, parsed.forks);
            return;
          }
        }
      } catch (e) {
        // Ignore sessionStorage errors
      }
    }

    fetch("https://api.github.com/repos/" + REPO)
      .then(function (response) {
        if (!response.ok) return null;
        return response.json();
      })
      .then(function (data) {
        if (!data) return;
        const stars = data.stargazers_count;
        const forks = data.forks_count;
        updateDOM(stars, forks);
        try {
          sessionStorage.setItem(
            CACHE_KEY,
            JSON.stringify({ stars: stars, forks: forks, timestamp: Date.now() })
          );
        } catch (e) {}
      })
      .catch(function () {
        // Fallback silently on network error
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fetchStats);
  } else {
    fetchStats();
  }
})();
