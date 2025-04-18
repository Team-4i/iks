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

        // Initialize audio
        this.sounds = {
            correct: new Audio('/static/hang/right_ans.mp3'),
            wrong: new Audio('/static/hang/wrong_ans.mp3'),
            gameOver: new Audio('/static/hang/game_over.mp3'),
            background: new Audio('/static/hang/game_sound_2.wav'),
            warning: new Audio('/static/hang/game_sound.wav')
        };

        // Set volume & loop for background
        this.sounds.background.loop = true;
        this.sounds.background.volume = 1.0;
        this.sounds.warning.loop = true;
        this.sounds.warning.volume = 1.0;
        this.sounds.correct.volume = 1.0;
        this.sounds.wrong.volume = 1.0;
        this.sounds.gameOver.volume = 1.0;
        
        this.isWarningSoundPlaying = false;
    }

    init() {
        this.setupEventListeners();
        this.startTimer();
        this.displayCurrentQuestion();
        this.updateStatsDisplay();
        this.hideAllParts();
        this.sounds.background.play().catch(e => console.log('Background music waiting for interaction.'));
        this.isWarningSoundPlaying = false;
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
            // All questions answered, end the game
            this.handleGameOver('questions_finished'); 
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
        const totalPairs = items.length;
        let matchedPairsCount = 0;
        
        let selectedItemButton = null;
        let selectedValueButton = null;
        let connectionLine = null;
        let correctPairs = []; // To store matched pairs with their connection lines

        // Create a visual connection line element
        const createConnectionLine = () => {
            const line = document.createElement('div');
            line.classList.add('match-line');
            container.appendChild(line);
            return line;
        };

        // Update the connection line between selected elements
        const updateConnectionLine = () => {
            if (!selectedItemButton || !selectedValueButton) return;
            
            if (!connectionLine) {
                connectionLine = createConnectionLine();
            }
            
            // Get positions
            const itemRect = selectedItemButton.getBoundingClientRect();
            const valueRect = selectedValueButton.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            
            // Calculate relative positions
            const startX = itemRect.right - containerRect.left;
            const startY = itemRect.top + (itemRect.height / 2) - containerRect.top;
            const endX = valueRect.left - containerRect.left;
            const endY = valueRect.top + (valueRect.height / 2) - containerRect.top;
            
            // Calculate line properties
            const length = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
            const angle = Math.atan2(endY - startY, endX - startX) * 180 / Math.PI;
            
            // Set line properties
            connectionLine.style.width = `${length}px`;
            connectionLine.style.left = `${startX}px`;
            connectionLine.style.top = `${startY}px`;
            connectionLine.style.transform = `rotate(${angle}deg)`;
            connectionLine.style.transformOrigin = '0 0';
            connectionLine.classList.add('active');
        };

        // Create two columns
        const itemsCol = document.createElement('div');
        const valuesCol = document.createElement('div');
        itemsCol.classList.add('match-column');
        valuesCol.classList.add('match-column');

        const shuffledValues = this.shuffleArray([...values]);

        const checkCompletion = () => {
            if (matchedPairsCount === totalPairs) {
                this.handleAnswer(true);
            }
        };

        const resetSelection = (isCorrect) => {
            if (!isCorrect) { // Only reset if incorrect match
                if (selectedItemButton) selectedItemButton.classList.remove('selected', 'incorrect');
                if (selectedValueButton) selectedValueButton.classList.remove('selected', 'incorrect');
                
                // Reset connection line only if incorrect
                if (connectionLine) {
                    connectionLine.classList.remove('active');
                    // Just hide it, don't remove
                    connectionLine.style.opacity = '0';
                }
            }
            
            selectedItemButton = null;
            selectedValueButton = null;
            
            if (!isCorrect) {
                connectionLine = null; // Create new for next pair only if incorrect
            }
        };

        const handleSelection = (button, type, value) => {
            if (button.disabled) return; // Ignore clicks on already matched items

            if (type === 'item') {
                if (selectedItemButton) selectedItemButton.classList.remove('selected');
                selectedItemButton = button;
                button.classList.add('selected');
            } else { // type === 'value'
                if (selectedValueButton) selectedValueButton.classList.remove('selected');
                selectedValueButton = button;
                button.classList.add('selected');
            }

            if (selectedItemButton && selectedValueButton) {
                // Update visual connection
                updateConnectionLine();
                
                // Check if match is correct after a short delay to show the connection
                setTimeout(() => {
                    const itemText = selectedItemButton.dataset.item;
                    const valueText = selectedValueButton.dataset.value;
                    const isCorrect = question.pairs[itemText] === valueText;

                    if (isCorrect) {
                        matchedPairsCount++;
                        
                        // Add classes for correct match
                        selectedItemButton.classList.add('correct');
                        selectedValueButton.classList.add('correct');
                        
                        // Remove "selected" class 
                        selectedItemButton.classList.remove('selected');
                        selectedValueButton.classList.remove('selected');
                        
                        // Disable the buttons
                        selectedItemButton.disabled = true;
                        selectedValueButton.disabled = true;
                        
                        // Format the connection line for correct match
                        if (connectionLine) {
                            connectionLine.style.backgroundColor = '#2ecc71'; // Green for correct
                            connectionLine.style.height = '3px'; // Thicker line
                            
                            // Store the correct pair and its line
                            correctPairs.push({
                                item: selectedItemButton,
                                value: selectedValueButton,
                                line: connectionLine
                            });
                        }
                        
                        // Reset selected references but keep the line
                        selectedItemButton = null;
                        selectedValueButton = null;
                        connectionLine = null; // Start fresh for next pair
                        
                        checkCompletion();
                    } else {
                        // Add classes for incorrect match
                        selectedItemButton.classList.add('incorrect');
                        selectedValueButton.classList.add('incorrect');
                        
                        // Format the connection line for incorrect match
                        if (connectionLine) {
                            connectionLine.style.backgroundColor = '#e74c3c'; // Red for incorrect
                        }
                        
                        // Reset after a longer delay to see the feedback
                        setTimeout(() => {
                            resetSelection(false);
                        }, 800);
                    }
                }, 300);
            }
        };

        items.forEach(item => {
            const button = document.createElement('button');
            button.textContent = item;
            button.classList.add('match-item');
            button.dataset.item = item; // Store item text
            button.addEventListener('click', () => handleSelection(button, 'item', item));
            itemsCol.appendChild(button);
        });

        shuffledValues.forEach(value => {
            const button = document.createElement('button');
            button.textContent = value;
            button.classList.add('match-value');
            button.dataset.value = value; // Store value text
            button.addEventListener('click', () => handleSelection(button, 'value', value));
            valuesCol.appendChild(button);
        });

        container.appendChild(itemsCol);
        container.appendChild(valuesCol);
        this.questionContentElement.appendChild(container);
        
        // Make positions recalculate on window resize
        window.addEventListener('resize', () => {
            correctPairs.forEach(pair => {
                const itemRect = pair.item.getBoundingClientRect();
                const valueRect = pair.value.getBoundingClientRect();
                const containerRect = container.getBoundingClientRect();
                
                const startX = itemRect.right - containerRect.left;
                const startY = itemRect.top + (itemRect.height / 2) - containerRect.top;
                const endX = valueRect.left - containerRect.left;
                const endY = valueRect.top + (valueRect.height / 2) - containerRect.top;
                
                const length = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
                const angle = Math.atan2(endY - startY, endX - startX) * 180 / Math.PI;
                
                pair.line.style.width = `${length}px`;
                pair.line.style.left = `${startX}px`;
                pair.line.style.top = `${startY}px`;
                pair.line.style.transform = `rotate(${angle}deg)`;
            });
        });
    }

    displayTrueFalse(question) {
        const container = document.createElement('div');
        container.classList.add('tf-options-container');
        
        ['True', 'False'].forEach(option => {
            const button = document.createElement('button');
            button.textContent = option;
            button.classList.add('tf-option');
            button.addEventListener('click', () => {
                const isCorrect = (option.toLowerCase() === question.correct_answer);
                this.handleAnswer(isCorrect);
            });
            container.appendChild(button);
        });
        
        this.questionContentElement.appendChild(container);
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
        
        const items = Object.keys(question.items);
        const totalItems = items.length;
        let correctlyCategorizedCount = 0;

        // Create category drop zones
        const categoryContainers = {};
        question.categories.forEach(category => {
            const categoryDiv = document.createElement('div');
            categoryDiv.classList.add('category-container');
            categoryDiv.dataset.category = category; // Store category name
            categoryDiv.innerHTML = `<h3>${category}</h3>`;
            
            categoryDiv.addEventListener('dragover', (e) => {
                e.preventDefault(); // Necessary to allow dropping
                categoryDiv.classList.add('drag-over');
            });
            categoryDiv.addEventListener('dragleave', () => {
                 categoryDiv.classList.remove('drag-over');
            });
            
            categoryDiv.addEventListener('drop', (e) => {
                e.preventDefault();
                categoryDiv.classList.remove('drag-over');
                const itemId = e.dataTransfer.getData('text/plain');
                const droppedItemElement = document.getElementById(`item-${itemId}`); // Get the element being dragged
                const targetCategory = categoryDiv.dataset.category;
                const correctCategory = question.items[itemId];

                if (droppedItemElement && !droppedItemElement.classList.contains('categorized')) {
                    if (targetCategory === correctCategory) {
                        categoryDiv.appendChild(droppedItemElement);
                        droppedItemElement.classList.add('categorized', 'correct');
                        droppedItemElement.draggable = false; // Prevent re-dragging
                        correctlyCategorizedCount++;

                        if (correctlyCategorizedCount === totalItems) {
                            this.handleAnswer(true);
                        }
                    } else {
                         // Incorrect drop - provide visual feedback (e.g., shake)
                        droppedItemElement.classList.add('incorrect-drop');
                        setTimeout(() => droppedItemElement.classList.remove('incorrect-drop'), 500);
                    }
                }
            });
            
            categoryContainers[category] = categoryDiv;
            container.appendChild(categoryDiv);
        });

        // Create draggable items container
        const itemsContainer = document.createElement('div');
        itemsContainer.classList.add('items-container');
        
        this.shuffleArray(items).forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('draggable-item');
            itemDiv.textContent = item;
            itemDiv.id = `item-${item}`; // Assign unique ID
            itemDiv.draggable = true;
            
            itemDiv.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', item);
                e.dataTransfer.effectAllowed = 'move';
                setTimeout(() => itemDiv.classList.add('dragging'), 0); // Style during drag
            });
             itemDiv.addEventListener('dragend', () => {
                itemDiv.classList.remove('dragging'); // Clean up style
            });
            
            itemsContainer.appendChild(itemDiv);
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
            this.sounds.correct.currentTime = 0;
            this.sounds.correct.play().catch(e => console.log('Error playing correct sound:', e));
        } else {
            this.timeLeft -= this.config.wrongAnswerPenalty;
            this.wrongAnswers++;
            
            feedbackElement.textContent = `Incorrect! -${this.config.wrongAnswerPenalty}s`;
            feedbackElement.classList.add('wrong-answer');
            this.sounds.wrong.currentTime = 0;
            this.sounds.wrong.play().catch(e => console.log('Error playing wrong sound:', e));
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
        
        if (this.timeLeft <= 10 && !this.isWarningSoundPlaying) {
            this.sounds.warning.play().catch(e => console.log('Warning sound waiting for interaction.'));
            this.isWarningSoundPlaying = true;
        } else if (this.timeLeft > 10 && this.isWarningSoundPlaying) {
            this.sounds.warning.pause();
            this.isWarningSoundPlaying = false;
        }
        
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
        this.sounds.background.pause();
        if (this.isWarningSoundPlaying) {
             this.sounds.warning.pause();
        }
    }

    resumeGame() {
        if (!this.isGameOver) {
            this.startTimer();
            this.sounds.background.play().catch(e => {});
            if (this.timeLeft <= 10 && this.isWarningSoundPlaying) {
                this.sounds.warning.play().catch(e => {}); 
            }
        }
    }

    handleGameOver(reason = 'unknown') {
        if (this.isGameOver) return;
        this.isGameOver = true;
        this.pauseGame();
        this.sounds.background.pause();
        if (this.isWarningSoundPlaying) {
             this.sounds.warning.pause();
             this.sounds.warning.currentTime = 0;
             this.isWarningSoundPlaying = false;
        }

        // Play game over sound
        this.sounds.gameOver.play().catch(e => console.log('Error playing game over sound:', e));

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
        } else if (reason === 'questions_finished') {
             gameOverMessage = `Congratulations! You answered all the questions.`;
        }
        
        gameOverMessage += `<br><br>Correct answers: ${this.correctAnswers}<br>Wrong answers: ${this.wrongAnswers}`;

        const modal = document.getElementById('game-over-modal');
        const messageEl = document.getElementById('game-over-message');
        
        if (modal && messageEl) {
            messageEl.innerHTML = gameOverMessage;
            modal.classList.add('show');
            
            // Update the stat cards with data
            document.getElementById('final-time').textContent = `${survivalTime}s`;
            document.getElementById('final-correct').textContent = this.correctAnswers;
            document.getElementById('final-wrong').textContent = this.wrongAnswers;
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