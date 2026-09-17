/**
 * static/hero.js
 * ================
 * Behavior for the huge-header hero section and its overlay mega menu.
 *
 * Adapted from "Codepen Challenge: Huge Headers/Mega Menus" by Sicontis
 * (https://codepen.io/Sicontis/pen/OJzOWxq), MIT License. The GSAP
 * clip-path reveal technique below is the original author's; the element
 * selectors, menu wiring, and helper functions were rewritten for
 * TripMate. Full credit in README.md.
 *
 * This file is kept separate from static/script.js on purpose: script.js
 * owns the actual "app" (sending a request, rendering results, PDF
 * export), while this file only owns the marketing-page hero/menu. Two
 * files with two clear jobs are easier to reason about than one big file
 * that does both.
 *
 * Load order matters here: index.html loads GSAP, then script.js, then
 * this file — GSAP must exist before we call gsap.timeline() below, and
 * script.js must exist before we call its setPrompt()/sendMessage()
 * helpers from planTripTo()/selectQuickPrompt() further down.
 */

const heroBurger = document.getElementById("hero-burger");
const megaMenu = document.querySelector(".mega-menu-overlay");

// Whether the mega menu is currently open. Mirrors the "active" class on
// the burger icon and the overlay's clip-path state.
let isMegaMenuOpen = false;

// Make sure the menu starts fully hidden. It also starts with a
// zero-area clip-path (set in style.css), so even before this line runs
// it wouldn't be visible — this just also removes it from layout/tab
// order entirely until it's opened.
megaMenu.style.display = "none";

/**
 * Reveal the mega menu with the same "wipe open" clip-path animation the
 * original CodePen used, then mark it open (both visually and for
 * accessibility via aria-expanded).
 */
function openMegaMenu() {
    isMegaMenuOpen = true;
    heroBurger.classList.add("active");
    heroBurger.setAttribute("aria-expanded", "true");

    megaMenu.style.display = "block";
    gsap.to(megaMenu, {
        duration: 1,
        clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)",
        ease: "expo.in",
    });
}

/**
 * Reverse the animation and hide the menu once it finishes closing.
 */
function closeMegaMenu() {
    isMegaMenuOpen = false;
    heroBurger.classList.remove("active");
    heroBurger.setAttribute("aria-expanded", "false");

    gsap.to(megaMenu, {
        duration: 1,
        clipPath: "polygon(0% 0%, 100% 0%, 100% 0%, 0% 0%)",
        ease: "expo.out",
        onComplete: () => {
            megaMenu.style.display = "none";
        },
    });
}

function toggleMegaMenu() {
    if (isMegaMenuOpen) {
        closeMegaMenu();
    } else {
        openMegaMenu();
    }
}

heroBurger.addEventListener("click", toggleMegaMenu);

// The burger has role="button" + tabindex="0" in the HTML so keyboard
// users can reach it with Tab; this makes Enter/Space activate it the
// same way a real <button> would.
heroBurger.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleMegaMenu();
    }
});

/**
 * Smoothly scroll down to the planner card. Used by the hero's
 * "Start Planning" button.
 */
function scrollToPlanner() {
    document.getElementById("plannerSection").scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}

/**
 * Called when the user clicks a destination pill in the mega menu (e.g.
 * "Japan"). Builds a reasonable default prompt for that destination,
 * drops it into the textarea via script.js's setPrompt(), then closes the
 * menu and scrolls down so the traveler immediately sees what was filled
 * in and can edit it before generating a plan.
 *
 * @param {string} destination - Human-readable place name, e.g. "Japan".
 */
function planTripTo(destination) {
    setPrompt(
        `Plan a 7 days trip to ${destination} including flights, hotels and sightseeing.`
    );
    closeMegaMenu();
    scrollToPlanner();
}

/**
 * Called when the user clicks one of the "Quick Prompts" items inside the
 * mega menu. These reuse the exact same prompt strings as the quick-prompt
 * buttons already on the planner card (static/script.js's setPrompt calls
 * in templates/index.html) — this is just a second, menu-accessible way
 * to reach the same shortcuts.
 *
 * @param {string} text - The full prompt text to fill into the textarea.
 */
function selectQuickPrompt(text) {
    setPrompt(text);
    closeMegaMenu();
    scrollToPlanner();
}

// ---------------------------------------------------------------------------
// Hero slider animation
// ---------------------------------------------------------------------------
//
// There are 5 slides (#hero-slide-1 .. #hero-slide-5). Each slide's
// headline (h2/h1/h3) and background image are hidden behind a zero-width
// clip-path "slit" on the left edge. The timeline below wipes the current
// slide's text/image away to the right, then wipes the next slide's
// text/image in from the left — repeating forever (repeat: -1) and
// reversing on each loop (yoyo: true) so it plays forward, then backward,
// then forward again.
//
// Note on GSAP syntax: the original CodePen used GSAP's older
// `.to(target, duration, { ...vars })` shorthand. This file uses GSAP 3's
// documented `.to(target, { duration, ...vars })` form instead, to match
// the GSAP 3 build loaded in index.html exactly — same animation, just the
// current API.

const SLIDE_COUNT = 5;
const SLIDE_DELAY_SECONDS = 3; // how long each slide stays fully visible

const heroTimeline = gsap.timeline({
    repeat: -1,
    yoyo: true,
    ease: "expo.out",
});

// Slide 1 starts fully visible (a "full rectangle" clip-path).
gsap.set("#hero-slide-1 h2, #hero-slide-1 h1, #hero-slide-1 h3", {
    clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)",
});

// Slides 2-5 start fully hidden (a zero-width "slit" clip-path on the left
// edge), ready to be wiped into view by the timeline below.
gsap.set(
    [
        "#hero-slide-2 h2, #hero-slide-3 h2, #hero-slide-4 h2, #hero-slide-5 h2,",
        "#hero-slide-2 h1, #hero-slide-3 h1, #hero-slide-4 h1, #hero-slide-5 h1,",
        "#hero-slide-2 h3, #hero-slide-3 h3, #hero-slide-4 h3, #hero-slide-5 h3",
    ].join(" "),
    { clipPath: "polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)" }
);

for (let i = 1; i < SLIDE_COUNT; i++) {
    const next = i + 1;

    heroTimeline
        // Wipe the current slide's headline out to the left...
        .to(`#hero-slide-${i} h2`, {
            duration: 0.9,
            clipPath: "polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)",
            delay: SLIDE_DELAY_SECONDS,
        })
        .to(
            `#hero-slide-${i} h1`,
            { duration: 0.9, clipPath: "polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)" },
            "-=0.3"
        )
        .to(
            `#hero-slide-${i} h3`,
            { duration: 0.9, clipPath: "polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)" },
            "-=0.3"
        )
        // ...and its background image along with it.
        .to(
            `#hero-slide-${i} .hsi-${i}`,
            { duration: 0.7, clipPath: "polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)" },
            "-=1"
        )
        // Then wipe the next slide's headline in from the left.
        .to(`#hero-slide-${next} h2`, {
            duration: 0.9,
            clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)",
        })
        .to(
            `#hero-slide-${next} h1`,
            { duration: 0.9, clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)" },
            "-=0.3"
        )
        .to(
            `#hero-slide-${next} h3`,
            { duration: 0.9, clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)" },
            "-=0.3"
        );
}
