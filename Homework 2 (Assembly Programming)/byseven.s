.data
entern: .asciiz "Enter N:" 
newline: .asciiz "\n"

.text

main:
   li $v0, 4 
   la $a0, entern
   syscall

   li $v0, 5
   syscall
   move $t0, $v0

   li $t1, 0
   li $t2, 1

loop:
   beq $t1, $t0, exit
   move $t3, $t2

loopdois:
   blt $t3, 7, exitpartial
   sub $t3, $t3, 7
   beq $t3, 0, divseven
   j loopdois

divseven:
   li $v0, 1
   move $a0, $t2
   syscall

   li $v0, 4
   la $a0, newline
   syscall

   addi $t1, $t1, 1
   j exitpartial

exitpartial:
   addi $t2, $t2, 1
   j loop

exit:
   jr $ra