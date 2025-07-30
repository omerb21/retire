/**
 * Client creation form handling
 * Includes validation, form submission, and error handling
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get form and form elements
    const form = document.getElementById('create-client-form');
    const idNumberInput = document.getElementById('id_number_raw');
    const fullNameInput = document.getElementById('full_name');
    const birthDateInput = document.getElementById('birth_date');
    const currentEmployerCheckbox = document.getElementById('current_employer_exists');
    const plannedTerminationDateGroup = document.getElementById('planned_termination_date_group');
    const plannedTerminationDateInput = document.getElementById('planned_termination_date');
    const submitButton = document.getElementById('submit-button');
    const submitText = document.getElementById('submit-text');
    const submitSpinner = document.getElementById('submit-spinner');
    const successMessage = document.getElementById('success-message');
    const errorMessage = document.getElementById('error-message');
    const clientIdSpan = document.getElementById('client-id');
    
    // Set min date for birth date (120 years ago)
    const today = new Date();
    const minBirthDate = new Date();
    minBirthDate.setFullYear(today.getFullYear() - 120);
    
    // Set max date for birth date (18 years ago)
    const maxBirthDate = new Date();
    maxBirthDate.setFullYear(today.getFullYear() - 18);
    
    // Format dates for input elements
    const formatDateForInput = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };
    
    // Set min and max dates for birth date input
    birthDateInput.setAttribute('min', formatDateForInput(minBirthDate));
    birthDateInput.setAttribute('max', formatDateForInput(maxBirthDate));
    
    // Set min date for planned termination date and retirement target date (today)
    const todayFormatted = formatDateForInput(today);
    plannedTerminationDateInput.setAttribute('min', todayFormatted);
    document.getElementById('retirement_target_date').setAttribute('min', todayFormatted);
    
    // Show/hide planned termination date based on current employer checkbox
    currentEmployerCheckbox.addEventListener('change', function() {
        plannedTerminationDateGroup.style.display = this.checked ? 'block' : 'none';
        if (!this.checked) {
            plannedTerminationDateInput.value = '';
        }
    });
    
    // ID number input mask and validation
    idNumberInput.addEventListener('input', function(e) {
        // Allow only digits
        this.value = this.value.replace(/[^\d]/g, '');
        
        // Limit to 9 digits
        if (this.value.length > 9) {
            this.value = this.value.slice(0, 9);
        }
    });
    
    // Validate Israeli ID number
    function validateIsraeliID(id) {
        // Remove non-digits and pad with leading zeros
        id = id.replace(/\D/g, '').padStart(9, '0');
        
        if (id.length !== 9) {
            return false;
        }
        
        // Calculate checksum
        let sum = 0;
        for (let i = 0; i < 9; i++) {
            let digit = parseInt(id.charAt(i));
            // Apply weight (1 or 2) based on position
            let weight = (i % 2) === 0 ? 1 : 2;
            
            // Multiply by weight and sum digits if result > 9
            let value = digit * weight;
            if (value > 9) {
                value = Math.floor(value / 10) + (value % 10);
            }
            
            sum += value;
        }
        
        // Valid ID if sum is divisible by 10
        return (sum % 10) === 0;
    }
    
    // Form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Reset error messages
        clearErrors();
        
        // Validate form
        if (!validateForm()) {
            return;
        }
        
        // Disable submit button and show spinner
        setSubmitButtonLoading(true);
        
        // Collect form data
        const formData = new FormData(form);
        const clientData = {};
        
        // Convert FormData to JSON object
        formData.forEach((value, key) => {
            // Handle checkboxes
            if (key === 'self_employed' || key === 'current_employer_exists') {
                clientData[key] = value === 'on';
            } 
            // Skip empty values for optional fields
            else if (value !== '') {
                clientData[key] = value;
            }
        });
        
        // Submit form data to API
        try {
            const response = await fetch('/api/v1/clients', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(clientData)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Show success message
                showSuccessMessage(data.id);
                // Reset form
                form.reset();
            } else {
                // Handle validation errors
                if (response.status === 422 && data.detail) {
                    handleValidationErrors(data.detail);
                } else if (data.detail) {
                    // Show general error message
                    showErrorMessage(data.detail);
                } else {
                    showErrorMessage('שגיאה בלתי צפויה ביצירת לקוח חדש');
                }
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            showErrorMessage('שגיאה בתקשורת עם השרת');
        } finally {
            // Re-enable submit button and hide spinner
            setSubmitButtonLoading(false);
        }
    });
    
    // Validate form
    function validateForm() {
        let isValid = true;
        
        // Validate ID number
        const idNumber = idNumberInput.value.trim();
        if (!idNumber) {
            showFieldError('id_number_raw', 'תעודת זהות הינה שדה חובה');
            isValid = false;
        } else if (!validateIsraeliID(idNumber)) {
            showFieldError('id_number_raw', 'תעודת זהות אינה תקינה');
            isValid = false;
        }
        
        // Validate full name
        const fullName = fullNameInput.value.trim();
        if (!fullName) {
            showFieldError('full_name', 'שם מלא הינו שדה חובה');
            isValid = false;
        } else if (fullName.length < 2) {
            showFieldError('full_name', 'שם מלא חייב להכיל לפחות 2 תווים');
            isValid = false;
        }
        
        // Validate birth date
        const birthDate = birthDateInput.value;
        if (!birthDate) {
            showFieldError('birth_date', 'תאריך לידה הינו שדה חובה');
            isValid = false;
        } else {
            const birthDateObj = new Date(birthDate);
            if (birthDateObj > maxBirthDate) {
                showFieldError('birth_date', 'תאריך לידה לא הגיוני - גיל מינימלי הוא 18');
                isValid = false;
            } else if (birthDateObj < minBirthDate) {
                showFieldError('birth_date', 'תאריך לידה לא הגיוני - גיל מקסימלי הוא 120');
                isValid = false;
            }
        }
        
        // Validate planned termination date if current employer exists
        if (currentEmployerCheckbox.checked && plannedTerminationDateInput.value) {
            const plannedTerminationDate = new Date(plannedTerminationDateInput.value);
            if (plannedTerminationDate < today) {
                showFieldError('planned_termination_date', 'תאריך סיום העסקה חייב להיות היום או בעתיד');
                isValid = false;
            }
        }
        
        // Validate retirement target date if provided
        const retirementTargetDate = document.getElementById('retirement_target_date').value;
        if (retirementTargetDate) {
            const retirementDateObj = new Date(retirementTargetDate);
            if (retirementDateObj < today) {
                showFieldError('retirement_target_date', 'תאריך יעד לפרישה חייב להיות היום או בעתיד');
                isValid = false;
            }
        }
        
        // Validate email if provided
        const email = document.getElementById('email').value.trim();
        if (email && !validateEmail(email)) {
            showFieldError('email', 'כתובת אימייל לא תקינה');
            isValid = false;
        }
        
        return isValid;
    }
    
    // Validate email format
    function validateEmail(email) {
        const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        return re.test(email);
    }
    
    // Show field error
    function showFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${fieldId}-error`);
        
        if (field && errorElement) {
            field.classList.add('is-invalid');
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    }
    
    // Clear all errors
    function clearErrors() {
        // Clear field errors
        const errorElements = document.querySelectorAll('.invalid-feedback');
        const invalidFields = document.querySelectorAll('.is-invalid');
        
        errorElements.forEach(element => {
            element.textContent = '';
            element.style.display = 'none';
        });
        
        invalidFields.forEach(field => {
            field.classList.remove('is-invalid');
        });
        
        // Clear general error message
        errorMessage.style.display = 'none';
        errorMessage.textContent = '';
        
        // Hide success message
        successMessage.style.display = 'none';
    }
    
    // Handle validation errors from API
    function handleValidationErrors(errors) {
        if (Array.isArray(errors)) {
            errors.forEach(error => {
                if (error.loc && error.loc.length > 1) {
                    const fieldName = error.loc[1];
                    showFieldError(fieldName, error.msg);
                }
            });
        } else if (typeof errors === 'string') {
            showErrorMessage(errors);
        }
    }
    
    // Show general error message
    function showErrorMessage(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        
        // Scroll to error message
        errorMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    // Show success message
    function showSuccessMessage(clientId) {
        clientIdSpan.textContent = clientId;
        successMessage.style.display = 'block';
        
        // Scroll to success message
        successMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    // Set submit button loading state
    function setSubmitButtonLoading(isLoading) {
        if (isLoading) {
            submitText.style.display = 'none';
            submitSpinner.style.display = 'inline-block';
            submitButton.disabled = true;
        } else {
            submitText.style.display = 'inline';
            submitSpinner.style.display = 'none';
            submitButton.disabled = false;
        }
    }
});
