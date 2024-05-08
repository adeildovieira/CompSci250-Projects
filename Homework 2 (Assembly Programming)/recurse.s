.data
enter: .asciiz "Your N is: "

.text

main:
	subu $sp, $sp, 32
	sw $ra, 0($sp)

    li $v0, 4
    la $a0, enter

    syscall
	
	li $v0, 5
	syscall

	move $a0, $v0

	jal torecurse

	move $a0, $v0
    
	li $v0, 1

	syscall

	lw $ra, 0($sp)
	addu $sp, $sp, 32
	jr $ra

torecurse:

	subu $sp, $sp, 32
	sw $ra, 0($sp)
	beqz $a0, basecase
	sw $a0, 4($sp)
	addi $a0, $a0, -1
	jal torecurse
	
	lw $t0, 4($sp)
	li $t1, 3

	add $t2, $t0, -1
    add $v0, $v0, 1

    mul $t2, $t1, $t2

    add $v0, $t2, $v0

	b returnrecursion

basecase:
	li $v0, 2

returnrecursion:
	lw $ra, 0($sp)
	addu $sp, $sp, 32
	jr $ra