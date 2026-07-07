/**
 * Crop Yield Prediction System - Custom JavaScript
 * Michael Okpara University of Agriculture, Umudike
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Form validation enhancements
    var forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Numeric input validation (allow only numbers and decimal point)
    var numericInputs = document.querySelectorAll('input[type="number"]');
    numericInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            if (this.value && isNaN(parseFloat(this.value))) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
    });

    // Prediction form - auto-calculate planting day of year
    var plantingDateInput = document.querySelector('#planting_date');
    if (plantingDateInput) {
        plantingDateInput.addEventListener('change', function() {
            var date = new Date(this.value);
            if (!isNaN(date.getTime())) {
                var startOfYear = new Date(date.getFullYear(), 0, 0);
                var diff = date - startOfYear;
                var dayOfYear = Math.floor(diff / (1000 * 60 * 60 * 24));
                // Store in hidden field or display
                var doyDisplay = document.querySelector('#planting_doy_display');
                if (doyDisplay) {
                    doyDisplay.textContent = 'Day of Year: ' + dayOfYear;
                }
            }
        });
    }

    // Dashboard - quick stats animation
    var statNumbers = document.querySelectorAll('.stat-number');
    statNumbers.forEach(function(el) {
        var target = parseInt(el.textContent.replace(/,/g, ''));
        if (!isNaN(target)) {
            var current = 0;
            var increment = Math.ceil(target / 30);
            var interval = setInterval(function() {
                current += increment;
                if (current >= target) {
                    current = target;
                    clearInterval(interval);
                }
                el.textContent = current.toLocaleString();
            }, 50);
        }
    });

    // History table - search functionality
    var searchInput = document.querySelector('#historySearch');
    var historyTable = document.querySelector('#historyTable');
    if (searchInput && historyTable) {
        searchInput.addEventListener('keyup', function() {
            var searchText = this.value.toLowerCase();
            var rows = historyTable.querySelectorAll('tbody tr');
            rows.forEach(function(row) {
                var text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchText) ? '' : 'none';
            });
        });
    }

    // Export functionality for history
    var exportBtn = document.querySelector('#exportHistory');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            var table = document.querySelector('#historyTable');
            if (table) {
                // Simple CSV export
                var rows = table.querySelectorAll('tr');
                var csvData = [];
                rows.forEach(function(row) {
                    var cols = row.querySelectorAll('td, th');
                    var rowData = [];
                    cols.forEach(function(col) {
                        rowData.push('"' + col.textContent.trim() + '"');
                    });
                    csvData.push(rowData.join(','));
                });
                var csvString = csvData.join('\n');
                var blob = new Blob([csvString], { type: 'text/csv' });
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'predictions_export.csv';
                a.click();
                window.URL.revokeObjectURL(url);
            }
        });
    }

    // Form wizard progress indicator
    var formSteps = document.querySelectorAll('.form-step');
    if (formSteps.length > 0) {
        var progressBar = document.querySelector('#formProgress');
        var currentStep = 0;
        var totalSteps = formSteps.length;
        
        function updateProgress() {
            if (progressBar) {
                var percent = ((currentStep + 1) / totalSteps) * 100;
                progressBar.style.width = percent + '%';
                progressBar.textContent = Math.round(percent) + '%';
            }
        }
        
        // Show first step initially
        formSteps.forEach(function(step, index) {
            if (index === 0) {
                step.style.display = 'block';
            } else {
                step.style.display = 'none';
            }
        });
        updateProgress();
        
        // Handle next/prev buttons
        var nextBtns = document.querySelectorAll('.step-next');
        var prevBtns = document.querySelectorAll('.step-prev');
        
        nextBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (currentStep < totalSteps - 1) {
                    formSteps[currentStep].style.display = 'none';
                    currentStep++;
                    formSteps[currentStep].style.display = 'block';
                    updateProgress();
                }
            });
        });
        
        prevBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (currentStep > 0) {
                    formSteps[currentStep].style.display = 'none';
                    currentStep--;
                    formSteps[currentStep].style.display = 'block';
                    updateProgress();
                }
            });
        });
    }

    console.log('Crop Yield Prediction System initialized successfully.');
});

/**
 * Utility function to show loading spinner
 */
function showLoading() {
    var spinner = document.querySelector('#loadingSpinner');
    if (spinner) {
        spinner.style.display = 'block';
    }
}

/**
 * Utility function to hide loading spinner
 */
function hideLoading() {
    var spinner = document.querySelector('#loadingSpinner');
    if (spinner) {
        spinner.style.display = 'none';
    }
}

/**
 * Format number as currency or with commas
 */
function formatNumber(num) {
    return Number(num).toLocaleString();
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Validate phone number (Nigerian format)
 */
function isValidPhone(phone) {
    var re = /^0[789][01]\d{8}$/;
    return re.test(phone);
}