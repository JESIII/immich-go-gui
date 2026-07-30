// Client-side dynamic GitHub repository statistics fetcher (stars & forks)
(function () {
  const REPO = "shitan198u/immich-go-gui";
  const CACHE_KEY = "igg_gh_stats_cache";
  const CACHE_TTL_MS = 60 * 1000; // 1 minute cache TTL

  function updateDOM(stars, forks) {
    if (stars === undefined || stars === null) return;

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
        const starLi = factsUl.querySelector(".md-source__fact--stars");
        if (starLi) {
          starLi.textContent = stars.toLocaleString();
        } else {
          const newStarLi = document.createElement("li");
          newStarLi.className = "md-source__fact md-source__fact--stars";
          newStarLi.textContent = stars.toLocaleString();
          factsUl.insertBefore(newStarLi, factsUl.firstChild);
        }

        if (forks !== undefined && forks !== null) {
          const forkLi = factsUl.querySelector(".md-source__fact--forks");
          if (forkLi) {
            forkLi.textContent = forks.toLocaleString();
          } else {
            const newForkLi = document.createElement("li");
            newForkLi.className = "md-source__fact md-source__fact--forks";
            newForkLi.textContent = forks.toLocaleString();
            factsUl.appendChild(newForkLi);
          }
        }
      }
    });
  }

  function fetchStats() {
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
      } catch (e) {}
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
      .catch(function () {});
  }

  // Hook into MkDocs Material document$ observable if available, otherwise DOMContentLoaded
  if (typeof document$ !== "undefined") {
    document$.subscribe(fetchStats);
  } else {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fetchStats);
    } else {
      fetchStats();
    }
  }
})();
