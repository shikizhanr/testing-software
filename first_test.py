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
        pytest.fail("Не удалось найти ключевой элемент для начала теста. Смотрите HTML-код выше.")


def test_p1_max_possible_transfer_is_successful(browser):
    start_transfer(browser, balance=9999, reserved=0)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("9090")
    
    transfer_button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON))
    transfer_button.click()
    
    alert = WebDriverWait(browser, 10).until(EC.alert_is_present())
    assert "принят банком" in alert.text
    alert.accept()

def test_p1_transfer_button_not_visible_before_amount_input(browser):
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    
    try:
        browser.find_element(*Locators.TRANSFER_BUTTON)
        pytest.fail("Кнопка 'Перевести' не должна быть на странице до ввода суммы")
    except NoSuchElementException:
        pass

def test_p1_xss_injection_is_handled_in_card_field(browser):
    start_transfer(browser)
    xss_payload = "<script>document.body.innerHTML='XSS'</script>"
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys(xss_payload)

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("100")
    
    assert "XSS" not in browser.page_source

def test_p1_logo_is_present(browser):
    browser.get("http://localhost:8000")
    logo = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.F_BANK_LOGO))
    assert logo.is_displayed() and "F-Bank" in logo.text

def test_p1_balance_updates_in_real_time(browser):
    start_transfer(browser, balance=10000, reserved=0)
    initial_balance_element = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.RUBLE_BALANCE))
    initial_balance_text = initial_balance_element.text
    initial_balance = float(''.join(c for c in initial_balance_text if c.isdigit() or c=='.'))

    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("1000")
    
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON)).click()
    
    WebDriverWait(browser, 10).until(EC.alert_is_present()).accept()
    
    WebDriverWait(browser, 10).until_not(EC.text_to_be_present_in_element(Locators.RUBLE_BALANCE, initial_balance_text))
    final_balance_text = browser.find_element(*Locators.RUBLE_BALANCE).text
    final_balance = float(''.join(c for c in final_balance_text if c.isdigit() or c=='.'))
    assert final_balance == initial_balance - 1100