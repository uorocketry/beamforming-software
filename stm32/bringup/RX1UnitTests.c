/*
This file contains the following unit tests:
1. Pin Toggle / Sign of Life Unit Test
2. Phase Shifter SPI command transmission unit test.
3. VGA SPI command transmission unit Test.
4. VGA + Phase Shifter SPI command transmission at 'same time' (within clock cycle)
*/


//Unit test 1: Pin Toggle / Sign of Life Unit Test
//Image
/*
int main(void)
{
    rcc_clock_setup_in_hse_8mhz_out_48mhz();
    rcc_periph_clock_enable(RCC_GPIOA);
    gpio_mode_setup(gpioPort, GPIO_MODE_OUTPUT, GPIO_PUPD_NONE, gpioPin); // required

    while (1)
    {
        SignOfLifeSignalAtMaximumSpeed(SIGNOFLIFEPORT, SIGNOFLIFEPIN); //toggle at max speed by setting and resetting BSRR for the pin
    }

    return 0;
}
*/

//Unit test 2: Phase Shifter SPI command transmission unit test.
//Images:
// - RX1_RecreatePE448SpiTiming.png & RX1_RecreatePE448SpiTiming(2).png ("dont care" after LE set)
// - RX1_PE448SpiCmd.png (proof of correct cmd format)
/*
int main(void)
{
    rcc_clock_setup_in_hse_8mhz_out_48mhz();
    pe448spisetup();
    spi_enable(SPI2);

    // Other calibrated states can be selected by their CAN table index.
    uint8_t stateWordTableIndex = 146u; // approximately 205.3 degrees at 2.4 GHz
    optimizedPhaseState_e phaseState = GetOptimizedPhaseState(stateWordTableIndex);
    uint8_t unitAddressWord = 0b0011;
    uint16_t command = MakePSCommand(phaseState, unitAddressWord);

    while (1)
    {
        gpio_clear(BOARD_PHASE_LE_PORT, BOARD_PHASE_LE_PIN); //set the cs low
        spi_send(SPI2, command);
        gpio_set(BOARD_PHASE_LE_PORT, BOARD_PHASE_LE_PIN);
        //then send another command.
        spi_send(SPI2, 0b0011111100000); //LE indifference: "dont care" about this second command. whatever we send after LE goes high should be ignored. Tested by sending a command after LE goes high and ensuring that the response is not affected
        break;
    }
    return 0;
}
*/


//Unit test 3: VGA SPI command transmission unit Test.
/*
int main(void)
{
    rcc_clock_setup_in_hse_8mhz_out_48mhz();
    f0480spisetup();
    spi_enable(SPI1);
    uint8_t command = 0u;
    MakeVGACommand(23u, &command); // maximum attenuation, command 0b01011100

    while (1)
    {
    gpio_clear(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    spi_send(SPI1, command);
    gpio_set(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    break;
    }
    return 0;
}


//Unit test 4: sending a command to the phase shifter and the VGA at the same time.
int main(void)
{
    rcc_clock_setup_in_hse_8mhz_out_48mhz();
    f0480spisetup();
    pe448spisetup();
    spi_enable(SPI2);
    spi_enable(SPI1);

    uint8_t commandVGA = 0u;
    MakeVGACommand(23u, &commandVGA);
    uint16_t commandPS = MakePSCommand(GetOptimizedPhaseState(146u), 0b0011);

    // Other attenuation values can be formed with MakeVGACommand(0..23, &commandVGA).


    gpio_clear(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    gpio_clear(BOARD_PHASE_LE_PORT, BOARD_PHASE_LE_PIN);

    while (1)
    {
    spi_send(SPI2, commandPS);
    spi_send(SPI1, commandVGA);
    gpio_set(BOARD_VGA_CS_PORT, BOARD_VGA_CS_PIN);
    gpio_set(BOARD_PHASE_LE_PORT, BOARD_PHASE_LE_PIN);
    break;
    }
    return 0;
}

*/

