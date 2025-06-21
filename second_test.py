import pytest
import math
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

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


# --- Фикстура для инициализации и закрытия браузера ---
@pytest.fixture
def browser():
    print("\nНастройка драйвера для Edge")
    service = EdgeService(executable_path=EdgeChromiumDriverManager().install())
    options = webdriver.EdgeOptions()
    driver = webdriver.Edge(service=service, options=options)
    
    driver.implicitly_wait(5)
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
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("5000")
    
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON)).click()
    
    alert = WebDriverWait(browser, 10).until(EC.alert_is_present())
    assert "принят банком" in alert.text
    alert.accept()

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
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("123456789012345")
    
    try:
        browser.find_element(*Locators.TRANSFER_AMOUNT_INPUT)
        pytest.fail("Поле для ввода суммы не должно было появиться")
    except NoSuchElementException:
        pass

def test_p2_card_placeholder_text_is_correct(browser):
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    assert card_input.get_attribute("placeholder") == "0000 0000 0000 0000"