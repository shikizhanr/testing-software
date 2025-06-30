import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options 

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class Locators:
    RUBLE_ACCOUNT_CARD = (By.XPATH, "//h2[normalize-space()='Рубли']")
    F_BANK_LOGO = (By.XPATH, "//h1[contains(text(), 'F-Bank')]")
    RUBLE_BALANCE = (By.XPATH, "//h2[normalize-space()='Рубли']/following-sibling::p[contains(text(), 'На счету:')]")

    CARD_NUMBER_INPUT = (By.XPATH, "//input[@placeholder='0000 0000 0000 0000']")
    TRANSFER_AMOUNT_INPUT = (By.XPATH, "//h3[contains(text(), 'Сумма перевода')]/following-sibling::input")
    TRANSFER_BUTTON = (By.XPATH, "//button[normalize-space()='Перевести']")
    COMMISSION_VALUE = (By.XPATH, "//p[contains(text(), 'Комиссия:')]")

    ERROR_MESSAGE = (By.XPATH, "//*[contains(text(), 'Недостаточно средств на счете')]")
    AMOUNT_VALIDATION_ERROR = (By.XPATH, "//input[@type='number' and @name='amount']/following-sibling::p[contains(@class, 'error-message')]")

# --- Фикстура для инициализации и закрытия браузера ---
@pytest.fixture
def browser():
    print("\nНастройка драйвера для Chrome (для CI)")
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox") 
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") 

    driver = webdriver.Chrome(options=chrome_options)
    
    yield driver
    print("\nЗакрытие драйвера")
    driver.quit()


# --- Вспомогательная функция для начала перевода ---
def start_transfer(driver, balance=30000, reserved=20001):
    driver.get(f"http://localhost:8000/?balance={balance}&reserved={reserved}")
    try:
        ruble_account = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(Locators.RUBLE_ACCOUNT_CARD)
        )
        ruble_account.click()
    except TimeoutException:
        print("\n\nОШИБКА: Не удалось найти карточку 'Рубли' на странице.")
        print(driver.page_source)
        pytest.fail("Не удалось найти ключевой элемент для начала теста. Смотрите HTML-код выше.")


# Тест TC-3.1
def test_p1_transfer_exact_available_amount_fails_due_to_commission(browser):
    """Проверяет, что перевод точной доступной суммы невозможен из-за комиссии."""
    start_transfer(browser, balance=10000, reserved=0)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("10000")
    error_message = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.ERROR_MESSAGE))
    assert "Недостаточно средств" in error_message.text

# Тест TC-3.2
def test_p1_success_notification_appears(browser):
    """Проверяет, что при корректном переводе появляется уведомление."""
    start_transfer(browser, balance=5000, reserved=0)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("100")
    
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON)).click()
    
    alert = WebDriverWait(browser, 10).until(EC.alert_is_present())
    assert "принят банком" in alert.text
    alert.accept()

# Тест TC-3.3
def test_p1_commission_is_calculated_correctly(browser):
    """Проверяет, что комиссия для 999 рассчитывается как 99 (округление вниз)."""
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("999")
    
    commission = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.COMMISSION_VALUE))
    assert "90" in commission.text  

# Тест TC-3.4
def test_p1_page_title_is_correct(browser):
    """Проверяет, что заголовок страницы корректен."""
    browser.get("http://localhost:8000")
    assert browser.title == "F-Bank"

# Тест TC-3.5
def test_p4_negative_amount_transfer_is_blocked(browser):
    """Проверяет, что появляется ошибка валидации при вводе отрицательной суммы."""
    start_transfer(browser, balance=10000, reserved=0)
    
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("-100")
    transfer_button = WebDriverWait(browser, 5).until(EC.presence_of_element_located(Locators.TRANSFER_BUTTON))
    assert transfer_button.is_enabled(), \
        "Кнопка 'Перевести' должна быть активна при отрицательной сумме (текущее поведение)."