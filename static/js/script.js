(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        initFlashDismiss();
        initKeyboardShortcuts();
        initSuggestionNavigation();
        initSubmitFeedback();
        initIndexingStatus();
    });

    function initFlashDismiss() {
        var buttons = document.querySelectorAll(".flash-dismiss");
        buttons.forEach(function (button) {
            button.addEventListener("click", function () {
                var message = button.closest(".flash-message");
                if (!message) {
                    return;
                }
                var container = message.parentElement;
                message.remove();
                if (container && container.children.length === 0) {
                    container.remove();
                }
            });
        });
    }

    function initKeyboardShortcuts() {
        var searchInput = document.getElementById("search-input");
        if (!searchInput) {
            return;
        }

        document.addEventListener("keydown", function (event) {
            if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) {
                return;
            }
            var active = document.activeElement;
            var tag = active ? active.tagName : "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (active && active.isContentEditable)) {
                return;
            }
            event.preventDefault();
            searchInput.focus();
            searchInput.select();
        });
    }

    function initSuggestionNavigation() {
        var searchInput = document.getElementById("search-input");
        var suggestionsBox = document.getElementById("search-suggestions");
        if (!searchInput || !suggestionsBox) {
            return;
        }

        var activeIndex = -1;

        function getItems() {
            return Array.prototype.slice.call(suggestionsBox.querySelectorAll(".suggestion-item"));
        }

        function setActive(items, index) {
            items.forEach(function (item, idx) {
                if (idx === index) {
                    item.classList.add("is-active");
                    item.setAttribute("aria-selected", "true");
                    item.scrollIntoView({ block: "nearest" });
                } else {
                    item.classList.remove("is-active");
                    item.removeAttribute("aria-selected");
                }
            });
            activeIndex = index;
        }

        searchInput.addEventListener("input", function () {
            activeIndex = -1;
        });

        searchInput.addEventListener("keydown", function (event) {
            if (suggestionsBox.style.display === "none") {
                return;
            }
            var items = getItems();
            if (items.length === 0) {
                return;
            }

            if (event.key === "ArrowDown") {
                event.preventDefault();
                var next = activeIndex + 1;
                if (next >= items.length) {
                    next = 0;
                }
                setActive(items, next);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                var prev = activeIndex - 1;
                if (prev < 0) {
                    prev = items.length - 1;
                }
                setActive(items, prev);
            } else if (event.key === "Enter" && activeIndex >= 0 && items[activeIndex]) {
                event.preventDefault();
                items[activeIndex].click();
            } else if (event.key === "Escape") {
                suggestionsBox.innerHTML = "";
                suggestionsBox.style.display = "none";
                activeIndex = -1;
            }
        });
    }

    function initSubmitFeedback() {
        var forms = document.querySelectorAll(".search-form, .scan-form, .quick-scan-form");
        var trackedButtons = [];

        forms.forEach(function (form) {
            var button = form.querySelector('button[type="submit"]');
            if (!button) {
                return;
            }
            var originalText = button.textContent.trim();
            button.dataset.originalText = originalText;
            trackedButtons.push(button);

            form.addEventListener("submit", function () {
                var pendingLabel = "Working...";
                if (form.classList.contains("search-form")) {
                    pendingLabel = "Searching...";
                } else if (form.classList.contains("scan-form")) {
                    pendingLabel = "Scanning...";
                } else if (originalText === "Quick Scan") {
                    pendingLabel = "Scanning...";
                } else if (originalText === "Index Content" || originalText === "AI Index") {
                    pendingLabel = "Starting...";
                }

                window.setTimeout(function () {
                    button.disabled = true;
                    button.textContent = pendingLabel;
                }, 0);
            });
        });

        window.addEventListener("pageshow", function () {
            trackedButtons.forEach(function (button) {
                button.disabled = false;
                if (button.dataset.originalText) {
                    button.textContent = button.dataset.originalText;
                }
            });
        });
    }

    function initIndexingStatus() {
        var headerStatus = document.getElementById("header-status");
        var statusText = document.getElementById("index-status-text");
        var progressNote = document.getElementById("indexing-progress-note");
        if (!headerStatus || !statusText) {
            return;
        }

        var pollTimer = null;

        function formatNumber(value) {
            return typeof value === "number" ? value.toLocaleString() : String(value || 0);
        }

        function fetchStatus() {
            fetch("/indexing-status")
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Status unavailable");
                    }
                    return response.json();
                })
                .then(function (data) {
                    var total = data.total_files || 0;
                    var isContentBusy = Boolean(data.indexing_content);
                    var isEmbeddingBusy = Boolean(data.indexing_embeddings);
                    var isBusy = isContentBusy || isEmbeddingBusy;

                    if (isContentBusy) {
                        headerStatus.classList.add("is-busy");
                        statusText.textContent = "Indexing content...";
                        if (progressNote) {
                            progressNote.textContent =
                                "Content indexing running (" +
                                formatNumber(data.indexed_content) +
                                " indexed)";
                            progressNote.classList.add("is-visible");
                        }
                    } else if (isEmbeddingBusy) {
                        headerStatus.classList.add("is-busy");
                        statusText.textContent = "Building AI index...";
                        if (progressNote) {
                            progressNote.textContent =
                                "Semantic indexing running (" +
                                formatNumber(data.embedded_files) +
                                " embedded)";
                            progressNote.classList.add("is-visible");
                        }
                    } else {
                        headerStatus.classList.remove("is-busy");
                        statusText.textContent = formatNumber(total) + " files indexed";
                        if (progressNote) {
                            progressNote.textContent = "";
                            progressNote.classList.remove("is-visible");
                        }
                    }

                    if (isBusy) {
                        pollTimer = window.setTimeout(fetchStatus, 2500);
                    } else if (pollTimer) {
                        window.clearTimeout(pollTimer);
                        pollTimer = null;
                    }
                })
                .catch(function () {
                    // Keep static fallback label if status endpoint is unreachable.
                });
        }

        fetchStatus();
    }
})();
