import '@testing-library/jest-dom'

// jsdom does not implement scrollIntoView
if (typeof window !== "undefined") {
  window.HTMLElement.prototype.scrollIntoView = () => {}
}
