/**
 * LLM Analysis Quiz - Frontend JavaScript
 * Handles form submission, API communication, and results display
 */

// Configuration
const API_BASE_URL = 'http://localhost:5000'; // Change this when deployed

// DOM Elements
const quizForm = document.getElementById('quizForm');
const resultsSection = document.getElementById('results');
const submitBtn = document.getElementById('submitBtn');
const retryBtn = document.getElementById('retryBtn');
const scoreValue = document.getElementById('scoreValue');
const resultMessage = document.getElementById('resultMessage');
const feedbackContainer = document.getElementById('feedbackContainer');
const apiStatus = document.getElementById('apiStatus');

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    checkAPIStatus();
    setupEventListeners();
});

// ============================================================================
// EVENT LISTENERS
// ============================================================================

function setupEventListeners() {
    // Form submission
    quizForm.addEventListener('submit', handleSubmit);
    
    // Retry button
    retryBtn.addEventListener('click', resetQuiz);
}

// ============================================================================
// API STATUS CHECK
// ============================================================================

async function checkAPIStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            apiStatus.textContent = '✓ Online';
            apiStatus.className = 'online';
        } else {
            apiStatus.textContent = '✗ Offline';
            apiStatus.className = 'offline';
        }
    } catch (error) {
        apiStatus.textContent = '✗ Offline';
        apiStatus.className = 'offline';
        console.error('API health check failed:', error);
    }
}

// ============================================================================
// FORM SUBMISSION
// ============================================================================

async function handleSubmit(event) {
    event.preventDefault();
    
    // Get form data
    const formData = new FormData(quizForm);
    const submission = {
        secret: formData.get('secret').trim(),
        system_prompt: formData.get('systemPrompt').trim(),
        user_prompt: formData.get('userPrompt').trim(),
        api_endpoint: formData.get('apiEndpoint').trim()
    };
    
    // Show loading state
    setLoadingState(true);
    
    try {
        // Submit to API
        const response = await fetch(`${API_BASE_URL}/submit-quiz`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(submission)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        // Display results
        displayResults(result);
        
    } catch (error) {
        console.error('Submission error:', error);
        alert('Error submitting quiz. Please check that the backend is running and try again.\n\nError: ' + error.message);
    } finally {
        setLoadingState(false);
    }
}

// ============================================================================
// UI STATE MANAGEMENT
// ============================================================================

function setLoadingState(isLoading) {
    submitBtn.disabled = isLoading;
    
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    
    if (isLoading) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline-flex';
    } else {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

function resetQuiz() {
    // Hide results
    resultsSection.style.display = 'none';
    
    // Reset form
    quizForm.reset();
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================================
// RESULTS DISPLAY
// ============================================================================

function displayResults(result) {
    // Update score
    scoreValue.textContent = `${result.score}/${result.total}`;
    
    // Update message
    resultMessage.textContent = result.message;
    
    // Calculate percentage for styling
    const percentage = (result.score / result.total) * 100;
    
    // Style message based on score
    if (percentage === 100) {
        resultMessage.style.borderLeftColor = 'var(--success-color)';
        resultMessage.style.background = '#d1fae5';
    } else if (percentage >= 75) {
        resultMessage.style.borderLeftColor = '#10b981';
        resultMessage.style.background = '#d1fae5';
    } else if (percentage >= 50) {
        resultMessage.style.borderLeftColor = 'var(--warning-color)';
        resultMessage.style.background = '#fef3c7';
    } else {
        resultMessage.style.borderLeftColor = 'var(--error-color)';
        resultMessage.style.background = '#fee2e2';
    }
    
    // Display feedback for each question
    feedbackContainer.innerHTML = '';
    
    Object.entries(result.feedback).forEach(([key, feedback]) => {
        const feedbackItem = createFeedbackItem(key, feedback);
        feedbackContainer.appendChild(feedbackItem);
    });
    
    // Show results section
    resultsSection.style.display = 'block';
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function createFeedbackItem(questionKey, feedback) {
    const item = document.createElement('div');
    item.className = `feedback-item ${feedback.correct ? 'correct' : 'incorrect'}`;
    
    // Map question keys to readable titles
    const questionTitles = {
        'secret': 'Question 1: Secret Value',
        'system_prompt': 'Question 2: System Prompt Security',
        'user_prompt': 'Question 3: User Prompt Injection',
        'api_endpoint': 'Question 4: API Endpoint'
    };
    
    // Create HTML
    let html = `
        <div class="feedback-header">
            <span class="feedback-title">${questionTitles[questionKey] || questionKey}</span>
            <span class="feedback-badge ${feedback.correct ? 'correct' : 'incorrect'}">
                ${feedback.correct ? '✓ Correct' : '✗ Incorrect'}
            </span>
        </div>
        <div class="feedback-message">${feedback.message}</div>
    `;
    
    // Add LLM response if available
    if (feedback.llm_response) {
        html += `
            <div class="llm-response">
                <div class="llm-response-label">LLM Response:</div>
                ${escapeHtml(feedback.llm_response)}
            </div>
        `;
    }
    
    // Add hint if available
    if (feedback.hint) {
        html += `
            <div class="feedback-message" style="margin-top: 0.5rem; font-style: italic;">
                💡 ${feedback.hint}
            </div>
        `;
    }
    
    item.innerHTML = html;
    return item;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}