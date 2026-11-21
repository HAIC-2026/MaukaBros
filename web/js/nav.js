// Sticky top nav: show its bottom border only after the page has scrolled 20px, and publish its
// height as --nav (0 when it isn't pinned) so in-page jumps can land below it.
const nav = document.querySelector(".nav-glass");
if (nav) {
  const update = () => nav.classList.toggle("is-scrolled", window.scrollY > 20);
  const measure = () => document.documentElement.style.setProperty("--nav",
    (getComputedStyle(nav).position === "sticky" ? nav.offsetHeight : 0) + "px");
  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", measure);
  window.addEventListener("load", measure);
  // The bar can change height without a window resize (it widens when a district opens, fields come and go)
  if (window.ResizeObserver) new ResizeObserver(measure).observe(nav);
  update(); measure();
}
