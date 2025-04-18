class HangmanGame {
    constructor(gameData = {}) {
        this.config = {
            initialTime: 30,
            timerInterval: 1000,
            partOrder: ['head', 'body', 'left-arm', 'right-arm', 'left-leg', 'right-leg'],
            correctAnswerBonus: 10,
            wrongAnswerPenalty: 5,
            ...gameData
        };

        this.questions = this.config.questions || [];
        this.currentQuestionIndex = 0;
        this.correctAnswers = 0;
        this.wrongAnswers = 0;

        this.timeLeft = this.config.initialTime;
        this.currentPart = 0;
        this.timerInterval = null;
        this.isGameOver = false;
        this.startTime = Date.now();
        this.maxTime = this.config.initialTime;

        // DOM Elements
        this.questionTextElement = document.getElementById('question-text');
        this.questionContentElement = document.getElementById('question-content');
        this.statsElement = document.getElementById('game-stats');
    }

    init() {
        this.setupEventListeners();
        this.startTimer();
        this.displayCurrentQuestion();
        this.updateStatsDisplay();
        this.hideAllParts();
    }

    hideAllParts() {
        this.config.partOrder.forEach(partId => {
            const part = document.getElementById(partId);
            if (part) {
                part.classList.remove('visible');
            }
        });
    }

    // --- Question Display Methods ---
    displayCurrentQuestion() {
        if (!this.questionTextElement || !this.questionContentElement) return;

        if (this.currentQuestionIndex < this.questions.length) {
            const question = this.questions[this.currentQuestionIndex];
            this.questionTextElement.textContent = question.question;
            this.questionContentElement.innerHTML = '';

            switch (question.type) {
                case 'MCQ':
                    this.displayMCQ(question);
                    break;
                case 'FILL':
                    this.displayFillBlank(question);
                    break;
                case 'MATCH':
                    this.displayMatchPairs(question);
                    break;
                case 'TF':
                    this.displayTrueFalse(question);
                    break;
                case 'ODD':
                    this.displayOddOneOut(question);
                    break;
                case 'CAT':
                    this.displayCategorize(question);
                    break;
                case 'SCRAMBLE':
                    this.displayWordUnscramble(question);
                    break;
            }
        } else {
            this.currentQuestionIndex = 0;
            this.displayCurrentQuestion();
        }
    }

    displayMCQ(question) {
        question.options.forEach(option => {
            const button = document.createElement('button');
            button.textContent = option;
            button.classList.add('question-option');
            button.addEventListener('click', () => this.handleAnswer(option === question.correct_answer));
            this.questionContentElement.appendChild(button);
        });
    }

    displayFillBlank(question) {
        const container = document.createElement('div');
        container.classList.add('fill-blank-container');

        const hint = document.createElement('p');
        hint.textContent = `Hint: ${question.hint_pattern}`;
        hint.classList.add('hint-text');
        container.appendChild(hint);

        const input = document.createElement('input');
        input.type = 'text';
        input.classList.add('fill-blank-input');
        input.placeholder = 'Type your answer';
        container.appendChild(input);

        const submitBtn = document.createElement('button');
        submitBtn.textContent = 'Submit';
        submitBtn.classList.add('submit-button');
        submitBtn.addEventListener('click', () => {
            const isCorrect = input.value.toLowerCase() === question.answer.toLowerCase();
            this.handleAnswer(isCorrect);
        });
        container.appendChild(submitBtn);

        this.questionContentElement.appendChild(container);
    }

    displayMatchPairs(question) {
        const container = document.createElement('div');
        container.classList.add('match-pairs-container');

        const items = Object.keys(question.pairs);
        const values = Object.values(question.pairs);
        let selectedItem = null;
        let selectedValue = null;

        // Create two columns
        const itemsCol = document.createElement('div');
        const valuesCol = document.createElement('div');
        itemsCol.classList.add('match-column');
        valuesCol.classList.add('match-column');

        // Shuffle values
        const shuffledValues = this.shuffleArray([...values]);

        items.forEach(item => {
            const button = document.createElement('button');
            button.textContent = item;
            button.classList.add('match-item');
            button.addEventListener('click', () => {
                if (selectedValue) {
                    const isCorrect = question.pairs[item] === selectedValue;
                    this.handleAnswer(isCorrect);
                    selectedValue = null;
                } else {
                    selectedItem = item;
                    button.classList.add('selected');
                }
            });
            itemsCol.appendChild(button);
        });

        shuffledValues.forEach(value => {
            const button = document.createElement('button');
            button.textContent = value;
            button.classList.add('match-value');
            button.addEventListener('click', () => {
                if (selectedItem) {
                    const isCorrect = question.pairs[selectedItem] === value;
                    this.handleAnswer(isCorrect);
                    selectedItem = null;
                } else {
                    selectedValue = value;
                    button.classList.add('selected');
                }
            });
            valuesCol.appendChild(button);
        });

        container.appendChild(itemsCol);
        container.appendChild(valuesCol);
        this.questionContentElement.appendChild(container);
    }

    displayTrueFalse(question) {
        ['True', 'False'].forEach(option => {
            const button = document.createElement('button');
            button.textContent = option;
            button.classList.add('tf-option');
            button.addEventListener('click', () => {
                const isCorrect = (option === 'True') === question.correct_answer;
                this.handleAnswer(isCorrect);
            });
            this.questionContentElement.appendChild(button);
        });
    }

    displayOddOneOut(question) {
        question.options.forEach(option => {
            const button = document.createElement('button');
            button.textContent = option;
            button.classList.add('question-option');
            button.addEventListener('click', () => {
                const isCorrect = option === question.correct_answer;
                this.handleAnswer(isCorrect);
                if (isCorrect) {
                    this.showExplanation(question.explanation);
                }
            });
            this.questionContentElement.appendChild(button);
        });
    }

    displayCategorize(question) {
        const container = document.createElement('div');
        container.classList.add('categorize-container');

        // Create category containers
        const categoryContainers = {};
        question.categories.forEach(category => {
            const categoryDiv = document.createElement('div');
            categoryDiv.classList.add('category-container');
            categoryDiv.innerHTML = `<h3>${category}</h3>`;
            categoryContainers[category] = categoryDiv;
            container.appendChild(categoryDiv);
        });

        // Create draggable items
        const itemsContainer = document.createElement('div');
        itemsContainer.classList.add('items-container');
        
        const items = Object.keys(question.items);
        this.shuffleArray(items).forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('draggable-item');
            itemDiv.textContent = item;
            itemDiv.draggable = true;
            
            itemDiv.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', item);
            });
            
            itemsContainer.appendChild(itemDiv);
        });

        // Setup drop zones
        Object.values(categoryContainers).forEach(container => {
            container.addEventListener('dragover', (e) => {
                e.preventDefault();
            });
            
            container.addEventListener('drop', (e) => {
                e.preventDefault();
                const item = e.dataTransfer.getData('text/plain');
                const category = container.querySelector('h3').textContent;
                const isCorrect = question.items[item] === category;
                this.handleAnswer(isCorrect);
            });
        });

        container.appendChild(itemsContainer);
        this.questionContentElement.appendChild(container);
    }

    displayWordUnscramble(question) {
        const container = document.createElement('div');
        container.classList.add('scramble-container');

        const scrambledWord = document.createElement('p');
        scrambledWord.textContent = `Scrambled Word: ${question.scrambled_word}`;
        scrambledWord.classList.add('scrambled-word');
        container.appendChild(scrambledWord);

        if (question.hint) {
            const hint = document.createElement('p');
            hint.textContent = `Hint: ${question.hint}`;
            hint.classList.add('hint-text');
            container.appendChild(hint);
        }

        const input = document.createElement('input');
        input.type = 'text';
        input.classList.add('scramble-input');
        input.placeholder = 'Unscramble the word';
        container.appendChild(input);

        const submitBtn = document.createElement('button');
        submitBtn.textContent = 'Submit';
        submitBtn.classList.add('submit-button');
        submitBtn.addEventListener('click', () => {
            const isCorrect = input.value.toLowerCase() === question.correct_word.toLowerCase();
            this.handleAnswer(isCorrect);
        });
        container.appendChild(submitBtn);

        this.questionContentElement.appendChild(container);
    }

    showExplanation(explanation) {
        const explanationDiv = document.createElement('div');
        explanationDiv.classList.add('explanation');
        explanationDiv.textContent = explanation;
        this.questionContentElement.appendChild(explanationDiv);
    }

    handleAnswer(isCorrect) {
        const feedbackElement = document.createElement('div');
        feedbackElement.className = 'answer-feedback';
        
        if (isCorrect) {
            this.timeLeft += this.config.correctAnswerBonus;
            this.correctAnswers++;
            
            if (this.timeLeft > this.maxTime) {
                this.maxTime = this.timeLeft;
            }
            
            feedbackElement.textContent = `Correct! +${this.config.correctAnswerBonus}s`;
            feedbackElement.classList.add('correct-answer');
        } else {
            this.timeLeft -= this.config.wrongAnswerPenalty;
            this.wrongAnswers++;
            
            feedbackElement.textContent = `Incorrect! -${this.config.wrongAnswerPenalty}s`;
            feedbackElement.classList.add('wrong-answer');
        }
        
        this.questionContentElement.innerHTML = '';
        this.questionContentElement.appendChild(feedbackElement);
        
        this.updateTimerDisplay();
        this.updateStatsDisplay();
        
        if (this.timeLeft <= 0) {
            this.handleGameOver('time');
            return;
        }
        
        setTimeout(() => {
            this.currentQuestionIndex++;
            this.displayCurrentQuestion();
        }, 1000);
    }

    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
        return array;
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
            
            if (this.timeLeft <= 10) {
                timerDisplay.classList.add('warning');
            } else {
                timerDisplay.classList.remove('warning');
            }
        }
    }

    updateHangmanParts() {
        const totalParts = this.config.partOrder.length;
        const timeRatio = Math.max(0, Math.min(1, this.timeLeft / this.maxTime));
        const partsToShow = Math.floor((1 - timeRatio) * totalParts);
        
        for (let i = 0; i < totalParts; i++) {
            const partId = this.config.partOrder[i];
            const part = document.getElementById(partId);
            if (part) {
                if (i < partsToShow) {
                    if (!part.classList.contains('visible')) {
                        part.classList.add('visible');
                        if (i >= this.currentPart) {
                            this.triggerPartRevealEvent(partId);
                        }
                    }
                } else {
                    part.classList.remove('visible');
                }
            }
        }
        
        this.currentPart = partsToShow;
        
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
        if (this.isGameOver) return;
        this.isGameOver = true;
        this.pauseGame();

        if (reason === 'hanged') {
            this.config.partOrder.forEach((partId, index) => {
                const part = document.getElementById(partId);
                if (part) {
                    part.classList.add('visible');
                }
            });
            
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

        const modal = document.getElementById('game-over-modal');
        const messageEl = document.getElementById('game-over-message');
        
        if (modal && messageEl) {
            messageEl.innerHTML = gameOverMessage;
            modal.classList.add('show');
        }

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