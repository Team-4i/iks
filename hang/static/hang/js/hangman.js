class HangmanGame {
    constructor(config = {}) {
        // Default configuration that can be overridden
        this.config = {
            initialTime: 20,
            partRevealInterval: 3000,
            timerInterval: 1000,
            partOrder: ['head', 'body', 'left-arm', 'right-arm', 'left-leg', 'right-leg'],
            ...config
        };

        this.timeLeft = this.config.initialTime;
        this.currentPart = 0;
        this.timerInterval = null;
        this.partInterval = null;
        this.isGameOver = false;
    }

    init() {
        this.setupEventListeners();
        this.startTimer();
        this.startPartReveal();
    }

    setupEventListeners() {
        // Event listeners can be added here
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
        
        if (this.timeLeft <= 0) {
            this.handleGameOver();
        }
    }

    updateTimerDisplay() {
        const timerElement = document.getElementById('time');
        if (timerElement) {
            timerElement.textContent = this.timeLeft;
        }
    }

    startPartReveal() {
        this.partInterval = setInterval(() => {
            this.showNextPart();
        }, this.config.partRevealInterval);
    }

    showNextPart() {
        if (this.currentPart < this.config.partOrder.length) {
            const partId = this.config.partOrder[this.currentPart];
            this.showPart(partId);
            this.currentPart++;
            this.triggerPartRevealEvent(partId);
        }
    }

    showPart(partId) {
        const part = document.getElementById(partId);
        if (part) {
            part.classList.add('visible');
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
        // Handle game state changes
        const { type, data } = event.detail;
        switch(type) {
            case 'pause':
                this.pauseGame();
                break;
            case 'resume':
                this.resumeGame();
                break;
            case 'reset':
                this.resetGame();
                break;
        }
    }

    pauseGame() {
        clearInterval(this.timerInterval);
        clearInterval(this.partInterval);
    }

    resumeGame() {
        if (!this.isGameOver) {
            this.startTimer();
            this.startPartReveal();
        }
    }

    handleGameOver() {
        this.isGameOver = true;
        this.pauseGame();
        document.dispatchEvent(new CustomEvent('gameOver', {
            detail: {
                finalTime: this.timeLeft,
                partsRevealed: this.currentPart
            }
        }));
    }

    resetGame() {
        this.timeLeft = this.config.initialTime;
        this.currentPart = 0;
        this.isGameOver = false;
        
        // Reset UI
        this.updateTimerDisplay();
        this.config.partOrder.forEach(partId => {
            const part = document.getElementById(partId);
            if (part) {
                part.classList.remove('visible');
            }
        });
        
        // Restart game
        this.startTimer();
        this.startPartReveal();
    }
} 