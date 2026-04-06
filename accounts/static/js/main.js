(() => {
    const feedbackModal = document.getElementById("feedbackModal");
    if (!feedbackModal) {
        return;
    }

    const openButtons = document.querySelectorAll("[data-feedback-open]");
    const closeButtons = feedbackModal.querySelectorAll("[data-feedback-close]");
    const form = feedbackModal.querySelector("[data-feedback-form]");
    const successBox = feedbackModal.querySelector("[data-feedback-success]");
    const errorBox = feedbackModal.querySelector("[data-feedback-error]");
    const submitButton = feedbackModal.querySelector("[data-feedback-submit]");
    const ratingWidget = feedbackModal.querySelector("[data-feedback-rating]");
    const ratingInputs = Array.from(ratingWidget.querySelectorAll('input[name="rating"]'));
    const ratingText = feedbackModal.querySelector("[data-feedback-rating-text]");
    const ratingOptions = Array.from(feedbackModal.querySelectorAll(".feedback-rating-option"));
    const categoryInput = feedbackModal.querySelector("[data-feedback-category-input]");
    const categoryOptions = Array.from(feedbackModal.querySelectorAll(".feedback-category-option"));

    const ratingLabels = {
        1: "Poor",
        2: "Fair",
        3: "Good",
        4: "Very good",
        5: "Excellent",
    };

    const hideMessages = () => {
        successBox.textContent = "";
        errorBox.textContent = "";
        successBox.classList.add("d-none");
        errorBox.classList.add("d-none");
    };

    const clearErrors = () => {
        feedbackModal.querySelectorAll("[data-error-for]").forEach((node) => {
            node.textContent = "";
        });
    };

    const updateRatingOptions = (ratingValue) => {
        const numericValue = Number(ratingValue) || 0;
        ratingOptions.forEach((option) => {
            option.classList.toggle("is-active", Number(option.dataset.rating) <= numericValue);
        });
        ratingText.textContent = numericValue ? `${numericValue}/5 - ${ratingLabels[numericValue]}` : "Select a rating";
    };

    const getSelectedRating = () => {
        const selectedInput = ratingInputs.find((input) => input.checked);
        return selectedInput ? Number(selectedInput.value) : 0;
    };

    const openModal = () => {
        feedbackModal.classList.add("is-open");
        feedbackModal.setAttribute("aria-hidden", "false");
        document.body.classList.add("feedback-modal-open");
    };

    const closeModal = () => {
        feedbackModal.classList.remove("is-open");
        feedbackModal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("feedback-modal-open");
    };

    openButtons.forEach((button) => {
        button.addEventListener("click", openModal);
    });

    closeButtons.forEach((button) => {
        button.addEventListener("click", closeModal);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && feedbackModal.classList.contains("is-open")) {
            closeModal();
        }
    });

    ratingOptions.forEach((option) => {
        option.addEventListener("click", () => {
            const selectedInput = ratingWidget.querySelector(`#feedback-rating-${option.dataset.rating}`);
            if (selectedInput) {
                selectedInput.checked = true;
            }
            updateRatingOptions(option.dataset.rating);
            const ratingError = feedbackModal.querySelector('[data-error-for="rating"]');
            if (ratingError) {
                ratingError.textContent = "";
            }
        });

        option.addEventListener("mouseenter", () => {
            updateRatingOptions(option.dataset.rating);
        });
    });

    ratingWidget.addEventListener("mouseleave", () => {
        updateRatingOptions(getSelectedRating());
    });

    ratingInputs.forEach((input) => {
        input.addEventListener("change", () => {
            updateRatingOptions(input.value);
            const ratingError = feedbackModal.querySelector('[data-error-for="rating"]');
            if (ratingError) {
                ratingError.textContent = "";
            }
        });
    });

    categoryOptions.forEach((option) => {
        option.addEventListener("click", () => {
            categoryOptions.forEach((button) => button.classList.remove("is-active"));
            option.classList.add("is-active");
            if (categoryInput) {
                categoryInput.value = option.dataset.feedbackCategory || "";
            }
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        hideMessages();
        clearErrors();

        const formData = new FormData(form);
        if (!Number(formData.get("rating"))) {
            const ratingError = feedbackModal.querySelector('[data-error-for="rating"]');
            ratingError.textContent = "Please select a rating.";
            return;
        }

        submitButton.disabled = true;
        submitButton.textContent = "Submitting...";

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            const data = await response.json();
            if (!response.ok || !data.ok) {
                if (data.errors) {
                    Object.entries(data.errors).forEach(([fieldName, fieldErrors]) => {
                        const errorNode = feedbackModal.querySelector(`[data-error-for="${fieldName}"]`);
                        if (errorNode) {
                            errorNode.textContent = fieldErrors.join(" ");
                        }
                    });
                } else {
                    errorBox.textContent = "Something went wrong. Please try again.";
                    errorBox.classList.remove("d-none");
                }
                return;
            }

            successBox.textContent = data.message || "Feedback submitted successfully.";
            successBox.classList.remove("d-none");
            form.reset();
            updateRatingOptions(0);
            categoryOptions.forEach((button) => button.classList.remove("is-active"));
            if (categoryInput) {
                categoryInput.value = "";
            }
        } catch (error) {
            errorBox.textContent = "Unable to submit feedback right now. Please try again.";
            errorBox.classList.remove("d-none");
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Submit Feedback";
        }
    });

    updateRatingOptions(0);
})();
