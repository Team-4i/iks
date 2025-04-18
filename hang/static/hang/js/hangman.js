class HangmanGame {
    constructor(config = {}, mcqs = []) {
        this.config = {
            initialTime: 30,
            timerInterval: 1000,
            partOrder: ['head', 'body', 'left-arm', 'right-arm', 'left-leg', 'right-leg'],
            correctAnswerBonus: 10,
            wrongAnswerPenalty: 5,
            gameId: null,
            endGameUrl: null,
            csrfToken: null,
            startPageUrl: '/',
            ...config
        };

        this.mcqs = mcqs;
        this.currentMcqIndex = 0;
        this.correctAnswers = 0;
        this.wrongAnswers = 0;

        this.timeLeft = this.config.initialTime;
        this.currentPart = 0;
        this.timerInterval = null;
        this.isGameOver = false;
        this.startTime = Date.now();
        this.maxTime = this.config.initialTime; // Track the highest time value reached

        // DOM Elements for MCQs
        this.questionElement = document.getElementById('mcq-question');
        this.optionsElement = document.getElementById('mcq-options');
        this.statsElement = document.getElementById('game-stats');
    }

    init() {
        this.setupEventListeners();
        this.startTimer();
        this.displayCurrentMcq();
        this.updateStatsDisplay();
        this.hideAllParts(); // Ensure all parts start hidden
    }

    hideAllParts() {
        // Ensure all hangman parts are initially hidden
        this.config.partOrder.forEach(partId => {
            const part = document.getElementById(partId);
            if (part) {
                part.classList.remove('visible');
            }
        });
    }

    // --- MCQ Methods ---
    displayCurrentMcq() {
        if (!this.questionElement || !this.optionsElement) return;

        if (this.currentMcqIndex < this.mcqs.length) {
            const mcq = this.mcqs[this.currentMcqIndex];
            this.questionElement.textContent = mcq.question;
            this.optionsElement.innerHTML = '';

            mcq.options.forEach(option => {
                const button = document.createElement('button');
                button.textContent = option;
                button.classList.add('mcq-option-button');
                button.addEventListener('click', () => this.handleMcqAnswer(option, mcq.answer));
                this.optionsElement.appendChild(button);
            });
        } else {
            // When all questions are answered, cycle back to first question
            this.currentMcqIndex = 0;
            this.displayCurrentMcq();
        }
    }

    handleMcqAnswer(selectedOption, correctAnswer) {
        // Create feedback element
        const feedbackElement = document.createElement('div');
        feedbackElement.className = 'answer-feedback';
        
        if (selectedOption === correctAnswer) {
            // Correct answer: add time
            this.timeLeft += this.config.correctAnswerBonus;
            this.correctAnswers++;
            
            // Update max time if new time is higher
            if (this.timeLeft > this.maxTime) {
                this.maxTime = this.timeLeft;
            }
            
            feedbackElement.textContent = `Correct! +${this.config.correctAnswerBonus}s`;
            feedbackElement.classList.add('correct-answer');
        } else {
            // Wrong answer: subtract time
            this.timeLeft -= this.config.wrongAnswerPenalty;
            this.wrongAnswers++;
            
            feedbackElement.textContent = `Incorrect! -${this.config.wrongAnswerPenalty}s`;
            feedbackElement.classList.add('wrong-answer');
        }
        
        // Add feedback to the page
        this.optionsElement.innerHTML = '';
        this.optionsElement.appendChild(feedbackElement);
        
        // Update the timer display immediately
        this.updateTimerDisplay();
        this.updateStatsDisplay();
        
        // Check if time ran out due to wrong answer
        if (this.timeLeft <= 0) {
            this.handleGameOver('time');
            return;
        }
        
        // Show next question after a brief delay
        setTimeout(() => {
            this.currentMcqIndex++;
            this.displayCurrentMcq();
        }, 1000);
    }

    updateStatsDisplay() {
        if (this.statsElement) {
            this.statsElement.innerHTML = `
                <p>Correct Answers: ${this.correctAnswers}</p>
                <p>Wrong Answers: ${this.wrongAnswers}</p>
            `;
        }
    }

    // --- Timer and Game Flow Methods ---
    setupEventListeners() {
        document.addEventListener('gameStateChange', this.handleGameStateChange.bind(this));
    }

    startTimer() {
        this.updateTimerDisplay();
        this.timerInterval = setInterval(() => {
            this.updateTimer();
        }, this.config.timerInterval);
    }

    updateTimer() {
        this.timeLeft--;
        this.updateTimerDisplay();
        this.updateHangmanParts();
        
        if (this.timeLeft <= 0) {
            this.handleGameOver('time');
        }
    }

    updateTimerDisplay() {
        const timerElement = document.getElementById('time');
        const timerDisplay = document.getElementById('timer-display');
        
        if (timerElement) {
            timerElement.textContent = this.timeLeft >= 0 ? this.timeLeft : 0;
            
            // Add warning effect when time is running low (less than 10 seconds)
            if (this.timeLeft <= 10) {
                timerDisplay.classList.add('warning');
            } else {
                timerDisplay.classList.remove('warning');
            }
        }
    }

    updateHangmanParts() {
        // Calculate how many parts should be visible based on time left
        // 100% time = 0 parts, 0% time = all parts
        const totalParts = this.config.partOrder.length;
        const timeRatio = Math.max(0, Math.min(1, this.timeLeft / this.maxTime));
        const partsToShow = Math.floor((1 - timeRatio) * totalParts);
        
        // Update visibility of each part
        for (let i = 0; i < totalParts; i++) {
            const partId = this.config.partOrder[i];
            const part = document.getElementById(partId);
            if (part) {
                // Show parts that should be visible, hide others
                if (i < partsToShow) {
                    if (!part.classList.contains('visible')) {
                        part.classList.add('visible');
                        // If this is a newly shown part, trigger the event
                        if (i >= this.currentPart) {
                            this.triggerPartRevealEvent(partId);
                        }
                    }
                } else {
                    part.classList.remove('visible');
                }
            }
        }
        
        // Update current part count
        this.currentPart = partsToShow;
        
        // Check if all parts are shown (fully hanged)
        if (partsToShow >= totalParts) {
            this.handleGameOver('hanged');
        }
    }

    triggerPartRevealEvent(partId) {
        document.dispatchEvent(new CustomEvent('partRevealed', {
            detail: { 
                partId, 
                partNumber: this.currentPart 
            }
        }));
    }

    handleGameStateChange(event) {
        const { type } = event.detail;
        switch (type) {
            case 'pause': this.pauseGame(); break;
            case 'resume': this.resumeGame(); break;
            case 'reset': this.resetGame(); break;
        }
    }

    pauseGame() {
        clearInterval(this.timerInterval);
    }

    resumeGame() {
        if (!this.isGameOver) {
            this.startTimer();
        }
    }

    handleGameOver(reason = 'unknown') {
        if (this.isGameOver) return; // Prevent multiple calls
        this.isGameOver = true;
        this.pauseGame();

        // Ensure all parts are fully visible when game is over
        if (reason === 'hanged') {
            // Force show all parts
            this.config.partOrder.forEach((partId, index) => {
                const part = document.getElementById(partId);
                if (part) {
                    part.classList.add('visible');
                }
            });
            
            // Small delay to ensure animations complete before showing modal
            setTimeout(() => {
                this.showGameOverModal(reason);
            }, 500);
        } else {
            this.showGameOverModal(reason);
        }
    }
    
    showGameOverModal(reason) {
        const survivalTime = Math.max(0, Math.floor((Date.now() - this.startTime) / 1000));

        let gameOverMessage = `You survived for ${survivalTime} seconds.`;
        if (reason === 'time') {
            gameOverMessage = `Time's up! ${gameOverMessage}`;
        } else if (reason === 'hanged') {
            gameOverMessage = `You were hanged! ${gameOverMessage}`;
        }
        
        gameOverMessage += `<br><br>Correct answers: ${this.correctAnswers}<br>Wrong answers: ${this.wrongAnswers}`;

        // Update and show the modal
        const modal = document.getElementById('game-over-modal');
        const messageEl = document.getElementById('game-over-message');
        
        if (modal && messageEl) {
            messageEl.innerHTML = gameOverMessage;
            modal.classList.add('show');
        }

        // Send game data to server
        if (this.config.gameId && this.config.endGameUrl && this.config.csrfToken) {
            const formData = new FormData();
            formData.append('game_id', this.config.gameId);
            formData.append('survival_time', survivalTime);
            formData.append('parts_revealed', this.currentPart);
            formData.append('correct_answers', this.correctAnswers);
            formData.append('wrong_answers', this.wrongAnswers);

            fetch(this.config.endGameUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.config.csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status !== 'success') {
                    console.error("Failed to save game:", data.message);
                }
            })
            .catch(error => {
                console.error("Error sending game data:", error);
            });
        } else {
            console.warn("Game config missing. Score not saved.");
        }
    }

    resetGame() {
         if (this.config.startPageUrl) {
             window.location.href = this.config.startPageUrl;
         } else {
             console.error("Start page URL not configured for reset.");
             window.location.href = '/';
         }
    }
} 