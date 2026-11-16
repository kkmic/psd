# Benchmark build - STM32F405 (QEMU netduinoplus2 machine), Cortex-M4F hard float.
# Base: STM32CubeF4 ADC_RegularConversion_DMA example, RCC set to 168 MHz (M=4 N=168 P=2 Q=7).
# The same clock config applies to STM32F407 (identical clock tree / PLL limits).
CUBE    := /home/kirill/work/STM32CubeF4
HAL     := $(CUBE)/Drivers/STM32F4xx_HAL_Driver
CMSIS   := $(CUBE)/Drivers/CMSIS
DSPINC  := $(CMSIS)/DSP/Include
DSPPRIV := $(CMSIS)/DSP/PrivateInclude

CROSS   := arm-none-eabi-
CC      := $(CROSS)gcc
OBJDUMP := $(CROSS)objdump
SIZE    := $(CROSS)size

CPATH   := Inc \
           $(HAL)/Inc \
           $(HAL)/Inc/Legacy \
           $(CMSIS)/Device/ST/STM32F4xx/Include \
           $(CMSIS)/Include \
           $(DSPINC) \
           $(DSPPRIV)
INCLUDES := $(addprefix -I,$(CPATH))

CPUFLAGS := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
DEFS     := -DSTM32F405xx -DUSE_HAL_DRIVER -DARM_MATH_CM4

SRC_S := Src/startup_stm32f405xx.s
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

BUILD := build
ELF    := $(BUILD)/qemu_Os.elf
QEMU   := qemu-system-arm -M netduinoplus2 -cpu cortex-m4 -nographic \
          -semihosting-config enable=on,target=native

all: $(BUILD)/qemu_Os.elf $(BUILD)/qemu_O2.elf $(BUILD)/hw_Os.elf $(BUILD)/hw407_Os.elf

$(BUILD):
	mkdir -p $@

$(BUILD)/qemu_Os.elf: $(BUILD) $(SRC_C) $(SRC_S) $(SRC_COMMON)
	$(CC) $(CPUFLAGS) $(INCLUDES) $(DEFS) -DBENCH_QEMU -Os $(SRC_S) $(SRC_C) $(LDFLAGS) -o $@

$(BUILD)/qemu_O2.elf: $(BUILD) $(SRC_C) $(SRC_S) $(SRC_COMMON)
	$(CC) $(CPUFLAGS) $(INCLUDES) $(DEFS) -DBENCH_QEMU -O2 $(SRC_S) $(SRC_C) $(LDFLAGS) -o $@

$(BUILD)/hw_Os.elf: $(BUILD) $(SRC_C) $(SRC_S) $(SRC_COMMON)
	$(CC) $(CPUFLAGS) $(INCLUDES) $(DEFS) -Os $(SRC_S) $(SRC_C) $(SRC_HW) $(SRC_COMMON) $(LDFLAGS) -o $@

# flashable on the STM32F4-Discovery (STM32F407VG); semihosting output requires
# a debug session (ST-Link GDB server / STM32CubeIDE with semihosting enabled)
$(BUILD)/hw407_Os.elf: $(BUILD) $(SRC_C) $(SRC_S) $(SRC_COMMON)
	cp $(CUBE)/Drivers/CMSIS/Device/ST/STM32F4xx/Source/Templates/gcc/startup_stm32f407xx.s $(BUILD)/
	$(CC) $(CPUFLAGS) $(INCLUDES) -DSTM32F407xx -DUSE_HAL_DRIVER -DARM_MATH_CM4 -Os \
	      $(BUILD)/startup_stm32f407xx.s $(SRC_C) $(SRC_HW) $(SRC_COMMON) $(LDFLAGS) -o $@

disasm: $(BUILD)/qemu_Os.elf
	$(OBJDUMP) -d $< > $(BUILD)/qemu_Os.disasm

size: all
	$(SIZE) $(BUILD)/*.elf

# functional run + DWT availability probe
run: $(ELF)
	$(QEMU) -kernel $(ELF)

# instruction-trace run (single iteration, no chaining, deterministic):
# qemu.log holds TB traces; marker functions bracket each measurement
trace: $(BUILD)/qemu_I1.elf
	rm -f /tmp/qemu.log
	$(QEMU) -kernel $(BUILD)/qemu_I1.elf -d nochain,exec -D /tmp/qemu.log
	@echo "log lines: $$(wc -l < /tmp/qemu.log)"

$(BUILD)/qemu_I1.elf: $(BUILD) $(SRC_C) $(SRC_S) $(SRC_COMMON)
	$(CC) $(CPUFLAGS) $(INCLUDES) $(DEFS) -DBENCH_QEMU -DITERS=1 -Os $(SRC_S) $(SRC_C) $(LDFLAGS) -o $@

# single-step trace: every guest instruction is one Trace line in the log,
# so counting lines between two marker PCs yields exact instruction counts
trace1: $(BUILD)/qemu_I1.elf
	rm -f /tmp/qemu1.log
	$(QEMU) -kernel $(BUILD)/qemu_I1.elf -d nochain,exec -accel tcg,one-insn-per-tb=on -D /tmp/qemu1.log
	@echo "log lines: $$(wc -l < /tmp/qemu1.log)"

clean:
	rm -f $(BUILD)/*.elf $(BUILD)/*.map $(BUILD)/*.disasm

.PHONY: all disasm size run trace clean
