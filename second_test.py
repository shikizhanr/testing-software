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
        pytest.fail("Не удалось найти ключевой элемент для начала теста. Смотрите HTML-код выше.")  # я-ж-с н

def test_p2_successful_transfer_within_limit(browser):
    start_transfer(browser, balance=10000, reserved=1000)
    
    # Получаем баланс ДО перевода
    balance_element = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.RUBLE_BALANCE))
    balance_text = balance_element.text  # Пример: "На счету: 10 000 ₽"
    initial_balance = int(''.join(filter(str.isdigit, balance_text)))

    # Вводим данные карты и сумму
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("5000")

    # Чтение комиссии, если она есть
    commission = 0
    try:
        commission_text = browser.find_element(*Locators.COMMISSION_VALUE).text  # Например: "Комиссия: 10 ₽"
        commission = int(''.join(filter(str.isdigit, commission_text)))
    except NoSuchElementException:
        pass  # Если нет комиссии — окей

    # Выполняем перевод
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON)).click()
    alert = WebDriverWait(browser, 10).until(EC.alert_is_present())
    assert "принят банком" in alert.text
    alert.accept()

    # Получаем баланс ПОСЛЕ перевода
    new_balance_element = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.RUBLE_BALANCE))
    new_balance_text = new_balance_element.text
    new_balance = int(''.join(filter(str.isdigit, new_balance_text)))

    expected_balance = initial_balance - 5000 - commission
    assert new_balance == expected_balance, f"Ожидалось {expected_balance}, но получили {new_balance}"


def test_p2_letters_in_amount_field_fail(browser):
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("abc")
    
    assert amount_input.get_attribute("value").isalpha() is False

def test_p2_transfer_over_limit_fails(browser):
    start_transfer(browser, balance=10000, reserved=1000)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("9000")
    
    error_message = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.ERROR_MESSAGE))
    assert "Недостаточно средств" in error_message.text

def test_p2_15_digit_card_number_fails(browser):
    start_transfer(browser)
    
    # Ввод 15-значного номера карты
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("123456789012345")  # 15 цифр

    # Проверка: поле ввода суммы не появляется
    amount_fields = browser.find_elements(*Locators.TRANSFER_AMOUNT_INPUT)
    assert len(amount_fields) == 0, "Поле суммы не должно появляться при некорректном номере карты"

    # Проверка: отображается сообщение об ошибке
    error_text = "Номер карты должен состояться из 16 цифр"
    try:
        error_element = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.XPATH, f"//*[contains(text(), '{error_text}')]"))
        )
        assert error_text in error_element.text
    except TimeoutException:
        pytest.fail(f"Ожидалась ошибка: '{error_text}', но она не появилась.")


def test_p2_card_placeholder_text_is_correct(browser):
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    assert card_input.get_attribute("placeholder") == "0000 0000 0000 0000"