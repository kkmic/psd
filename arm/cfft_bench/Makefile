# Benchmark build - STM32F407VG on the STM32F4-Discovery board (ST-LINK/V2.1).
# Base: STM32CubeF4 ADC_RegularConversion_DMA example, RCC set to 168 MHz (M=4 N=168 P=2 Q=7).
# Flash, run and DWT readout all go through openocd (board/stm32f4discovery.cfg).
CUBE    := /home/kirill/work/STM32CubeF4
HAL     := $(CUBE)/Drivers/STM32F4xx_HAL_Driver
CMSIS   := $(CUBE)/Drivers/CMSIS
DSPINC  := $(CMSIS)/DSP/Include
DSPPRIV := $(CMSIS)/DSP/PrivateInclude

CROSS   := arm-none-eabi-
CC      := $(CROSS)gcc
OBJDUMP := $(CROSS)objdump
SIZE    := $(CROSS)size
GDB     := gdb-multiarch

CPATH   := Inc \
           $(HAL)/Inc \
           $(HAL)/Inc/Legacy \
           $(CMSIS)/Device/ST/STM32F4xx/Include \
           $(CMSIS)/Include \
           $(CMSIS)/Core/Include \
           $(DSPINC) \
           $(DSPPRIV)
INCLUDES := $(addprefix -I,$(CPATH))

CPUFLAGS := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
DEFS     := -DSTM32F407xx -DUSE_HAL_DRIVER -DARM_MATH_CM4

SRC_S := Src/startup_stm32f407vgtx.s
SRC_C := Src/main.c Src/system_stm32f4xx.c \
         dsp/arm_cfft_f32.c dsp/arm_cfft_radix8_f32.c dsp/arm_cfft_init_f32.c \
         dsp/arm_bitreversal2.c dsp/arm_cmplx_mag_f32.c \
         dsp/arm_common_tables.c dsp/arm_const_structs.c dsp/arm_sin_f32.c
SRC_COMMON := Src/syscalls.c Src/sysmem.c

SRC_HW := $(HAL)/Src/stm32f4xx_hal.c $(HAL)/Src/stm32f4xx_hal_cortex.c \
          $(HAL)/Src/stm32f4xx_hal_rcc.c $(HAL)/Src/stm32f4xx_hal_rcc_ex.c \
          $(HAL)/Src/stm32f4xx_hal_pwr.c $(HAL)/Src/stm32f4xx_hal_pwr_ex.c \
          $(HAL)/Src/stm32f4xx_hal_gpio.c

LDFLAGS := $(CPUFLAGS) -TSTM32F407VGTX_FLASH.ld \
           -Wl,--gc-sections -Wl,--start-group -lc -lm -Wl,--end-group \
           --specs=nano.specs --specs=nosys.specs

BUILD  := build
HW_ELF := $(BUILD)/hw_Os.elf
OCD    := openocd -f board/stm32f4discovery.cfg

all: $(HW_ELF)

$(BUILD):
	mkdir -p $@

$(HW_ELF): $(BUILD) $(SRC_C) $(SRC_S) $(SRC_COMMON)
	$(CC) $(CPUFLAGS) $(INCLUDES) $(DEFS) -Os $(SRC_S) $(SRC_C) $(SRC_HW) $(SRC_COMMON) $(LDFLAGS) -o $@

disasm: $(HW_ELF)
	$(OBJDUMP) -d $< > $(BUILD)/hw_Os.disasm

size: all
	$(SIZE) $(HW_ELF)

# flash + run: semihosting prints (DWT CYCCNT results) appear on stdout;
# the firmware signals completion with semihosting SYS_EXIT.
flash: $(HW_ELF)
	$(OCD) -c "init" \
	       -c "arm semihosting enable" \
	       -c "reset halt" \
	       -c "program $(HW_ELF) verify" \
	       -c "reset run" \
	       -c "sleep 60000" \
	       -c "shutdown"

# start openocd as the debug server (gdb on 3333, telnet on 4444)
server:
	$(OCD)

# read the DWT registers via gdb while an openocd server (`make server`) is running
dwt:
	$(GDB) -batch -ex "target remote :3333" \
	       -ex 'printf "DWT_CTRL  = 0x%08x\n", *(unsigned int*)0xE0001000' \
	       -ex 'printf "DWT_CYCCNT = %u cycles\n", *(unsigned int*)0xE0001004' \
	       -ex 'printf "DEMCR     = 0x%08x\n", *(unsigned int*)0xE000EDFC' \
	       -ex "detach"

clean:
	rm -f $(BUILD)/*.elf $(BUILD)/*.map $(BUILD)/*.disasm

.PHONY: all disasm size flash server dwt clean
