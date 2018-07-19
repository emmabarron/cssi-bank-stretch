console.log('scripting');

const transactionTypes = ['deposit', 'withdraw', 'transfer'];

const transactionButtons = {};
const transactionPopups = {};
transactionTypes.forEach((type) => {
  transactionButtons[type] = document.querySelector('#' + type + '-button');
  transactionPopups[type] = document.querySelector('#' + type + '-popup');
});

document.addEventListener('click', (event) => {
  transactionTypes.forEach((type) => {
    const button = transactionButtons[type];
    const popup = transactionPopups[type];
    if (event.target == button) {
      if (!popup.classList.contains('showing')) {
        showFormOnButton(popup, button);
      } else {
        popup.classList.remove('showing');
      }
    } else if (!popup.contains(event.target)) {
      popup.classList.remove('showing');
    }
  });
})

function showFormOnButton(form, button) {
  buttonLocation = button.getBoundingClientRect();
  form.style.left = buttonLocation.x + 'px';
  form.style.top = (buttonLocation.y + buttonLocation.height) + 'px';
  form.classList.add('showing');
  form.querySelector('input').focus();
}
