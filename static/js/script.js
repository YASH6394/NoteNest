const menuToggle = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#primary-navigation");

if (menuToggle && navigation) {
    menuToggle.addEventListener("click", () => {
        const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
        menuToggle.setAttribute("aria-expanded", String(!isExpanded));
        menuToggle.setAttribute("aria-label", isExpanded ? "Open navigation menu" : "Close navigation menu");
        navigation.classList.toggle("is-open", !isExpanded);
    });

    navigation.addEventListener("click", (event) => {
        if (event.target.closest("a")) {
            menuToggle.setAttribute("aria-expanded", "false");
            menuToggle.setAttribute("aria-label", "Open navigation menu");
            navigation.classList.remove("is-open");
        }
    });
}

const searchForm = document.querySelector("#notes-search");
const searchInput = document.querySelector("#search-input");

if (searchForm && searchInput) {
    const filterCards = (selector, emptyMessageId, query) => {
        const cards = document.querySelectorAll(selector);
        let visibleCount = 0;

        cards.forEach((card) => {
            const searchText = card.dataset.search.toLowerCase();
            const isMatch = searchText.includes(query);
            card.hidden = !isMatch;
            if (isMatch) {
                visibleCount += 1;
            }
        });

        document.querySelector(emptyMessageId).hidden = visibleCount > 0;
    };

    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim().toLowerCase();
        filterCards(".subject-card", "#subject-empty", query);
        filterCards(".note-card", "#notes-empty", query);
    });

    searchForm.addEventListener("submit", (event) => {
        event.preventDefault();
        document.querySelector("#subjects").scrollIntoView({ behavior: "smooth" });
    });
}

document.querySelectorAll(".delete-note-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm("Delete this note and its PDF? This cannot be undone.")) {
            event.preventDefault();
        }
    });
});
