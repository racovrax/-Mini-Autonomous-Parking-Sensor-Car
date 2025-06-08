from machine import Pin, I2C, PWM, UART, time_pulse_us
from time    import sleep
import ssd1306

# 1. HC-SR04 ultrasonic setup
trig = Pin(18, Pin.OUT)
echo = Pin(19, Pin.IN)
def get_distance_cm():
    trig.low()
    sleep(0.05)
    trig.high()
    sleep(10e-6)
    trig.low()
    d = time_pulse_us(echo, 1, 30000)
    if d < 0:
        return None
    return (d/2) / 29.1

# 2. OLED SSD1306 I²C setup
i2c  = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
def display_distance(d):
    oled.fill(0)
    if d is None:
        oled.text("Fara ecou", 0, 0)
    else:
        oled.text("Distanta:", 0, 0)
        oled.text("{:5.1f} cm".format(d), 0, 16)
    oled.show()

# 3. Buzzer + LED
buzzer = Pin(6,  Pin.OUT, value=0)
led    = Pin(15, Pin.OUT, value=0)

# 4. Motoare pe PPM, cu inversare pentru pin16
motor_left  = PWM(Pin(16))
motor_right = PWM(Pin(17))
PWM_FREQ    = 333
PERIOD_US   = int(1_000_000 / PWM_FREQ)
motor_left.freq(PWM_FREQ)
motor_right.freq(PWM_FREQ)

def set_pulse(pwm, width_us, invert=False):
    # limitează la 500–2500 µs şi converteşte în duty_u16
    w = min(max(width_us, 500), 2500)
    if invert:
        # reflectă în jurul punctului de stop 1500 µs
        w = 3000 - w
    duty = int((w / PERIOD_US) * 65535)
    pwm.duty_u16(duty)

# valori prestabilite
pw_forward_left   = 400
pw_forward_right  = 1000
pw_stop           = 1500

# 5. UART pentru HC-05 pe GP0/GP1
# bt = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
bt = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))

# iniţial pornire
set_pulse(motor_left,  pw_forward_left,  invert=True)
set_pulse(motor_right, pw_forward_right, invert=False)

while True:
    # 1. Măsurare distanţă şi afişare
    dist = get_distance_cm()
    msg  = "timeout" if dist is None else "{:.1f} cm".format(dist)
    print("Distanta:", msg)
    display_distance(dist)

    # 2. Transmitere prin Bluetooth
    if dist is None:
        bt.write("Fara ecou\r\n")
    else:
        bt.write("Distanta: {:.1f} cm\r\n".format(dist))

    # 3. Comenzi manuale prin Bluetooth
    if bt.any():
        cmd = bt.read(1)
        print("cmd ", cmd)
        if cmd in (b'O', b'F'):      # start manual
            set_pulse(motor_left,  pw_forward_left,  invert=True)
            set_pulse(motor_right, pw_forward_right, invert=False)
        elif cmd in (b'X', b'S'):    # stop manual
            print("BT UART STOP RECEIVED")
            set_pulse(motor_left,  pw_stop, invert=True)
            set_pulse(motor_right, pw_stop, invert=False)

    # 4. Logică automată cu restart la dispariţia obstacolului
    if dist is not None and dist < 40:
        # obstacol detectat → opreşte şi semnalează
        set_pulse(motor_left,  pw_stop, invert=True)
        set_pulse(motor_right, pw_stop, invert=False)
        buzzer.value(1)
        led.value(1)
    else:
        # niciun obstacol → porneşte automat
        set_pulse(motor_left,  pw_forward_left,  invert=True)
        set_pulse(motor_right, pw_forward_right, invert=False)
        buzzer.value(0)
        led.value(0)

    sleep(0.1)
