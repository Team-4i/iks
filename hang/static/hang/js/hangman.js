class HangmanGame {
    constructor(config = {}) {
        // Default configuration
        this.config = {
            initialTime: 60,
            partRevealInterval: 10,
            timeDecrementInterval: 1000,
            partRevealOrder: ['head', 'body', 'leftArm', 'rightArm', 'leftLeg', 'rightLeg'],
            ...config
        };

        this.timeLeft = this.config.initialTime;
        this.currentPart = 0;
        this.timerInterval = null;
        this.isGameOver = false;
        this.partTimings = new Map(); // Store custom timing for each part
    }

    init() {
        this.setupEventListeners();
        this.startTimer();
    }

    setupEventListeners() {
        // Add any event listeners here
        document.addEventListener('gameOver', () => this.handleGameOver());
    }

    setPartTiming(partId, timing) {
        this.partTimings.set(partId, timing);
    }

    setPartRevealOrder(order) {
        this.config.partRevealOrder = order;
    }

    showPart(partId) {
        const part = document.getElementById(partId);
        if (part) {
            part.classList.remove('hidden');
            part.classList.add('reveal');
        }
    }

    showNextPart() {
        if (this.currentPart < this.config.partRevealOrder.length) {
            const partId = this.config.partRevealOrder[this.currentPart];
            this.showPart(partId);
            this.currentPart++;
            
            // Trigger custom event
            document.dispatchEvent(new CustomEvent('partRevealed', {
                detail: { partId, partNumber: this.currentPart }
            }));
        }
    }

    updateTimer() {
        this.timeLeft--;
        document.getElementById('time').textContent = this.timeLeft;
        
        if (this.timeLeft <= 0) {
            this.handleGameOver();
        } else {
            // Check if it's time to reveal next part based on custom timing
            const currentPartId = this.config.partRevealOrder[this.currentPart];
            const customTiming = this.partTimings.get(currentPartId);
            
            if (customTiming) {
                if (this.timeLeft % customTiming === 0) {
                    this.showNextPart();
                }
            } else if (this.timeLeft % this.config.partRevealInterval === 0) {
                this.showNextPart();
            }
        }
    }

    startTimer() {
        this.timerInterval = setInterval(() => this.updateTimer(), this.config.timeDecrementInterval);
    }

    pauseGame() {
        clearInterval(this.timerInterval);
    }

    resumeGame() {
        if (!this.isGameOver) {
            this.startTimer();
        }
    }

    handleGameOver() {
        this.isGameOver = true;
        clearInterval(this.timerInterval);
        document.dispatchEvent(new CustomEvent('gameOver', {
            detail: { finalTime: this.timeLeft }
        }));
    }

    resetGame() {
        this.timeLeft = this.config.initialTime;
        this.currentPart = 0;
        this.isGameOver = false;
        
        // Reset all parts to hidden
        this.config.partRevealOrder.forEach(partId => {
            const part = document.getElementById(partId);
            if (part) {
                part.classList.add('hidden');
                part.classList.remove('reveal');
            }
        });
        
        document.getElementById('time').textContent = this.timeLeft;
        this.startTimer();
    }
} 