.data
    bldgname: .asciiz "Insert building name: "
    bldgsqft: .asciiz "Building square footage: "
    bldgenergy: .asciiz "Annual energy (kWh): "
    nl: .asciiz "\n"
    doneing: .asciiz "DONE\n"
    betweenb: .asciiz " "
    zerofl: .float 0.000
.text

main:
    addi $sp, $sp, -28
    sw $ra, 0($sp)
    sw $s0, 4($sp)
    sw $s1, 8($sp)
    sw $s2, 12($sp)
    sw $s3, 16($sp)
    sw $s4, 20($sp)
    sw $s5, 24($sp)
    li $v0, 9
    la $a0, 72
    syscall
    move $s0, $v0
    li $v0, 4
    la $a0, bldgname
    syscall
    li $v0, 8           
    move $a0, $s0
    la $a1, 63
    syscall
    move $t4, $s0
    bldglpai:
    li $t6, 10 
    lb $t3, 0($t4)
    beq $t6, $t3, mo
    addi $t4, $t4, 1
    j bldglpai
    mo:
    sb $zero, 0($t4)
    li $v0, 4           
    la $a0, bldgsqft       
    syscall
    li $v0, 5               
    syscall
    move $t0, $v0           
    li $v0, 4
    la $a0, bldgenergy
    syscall
    li $v0, 6
    syscall
    beq  $t0, $zero, nothingzzz
    mov.s $f1, $f0              
    mtc1 $t0, $f0
    cvt.s.w $f0, $f0
    div.s $f0, $f1, $f0
    j     blgdsmm

nothingzzz:
    l.s   $f0, zerofl

blgdsmm:
    swc1 $f0, 64($s0)
    li $s3, 1
    li $v0, 9
    la $a0, 72
    syscall
    move $s1, $v0
    sw $s0, 68($s1)

bldgls:
    la $t5, doneing
    li $v0, 9
    la $a0, 72
    syscall
    move $t7, $v0
    li $v0, 4
    la $a0, bldgname
    syscall
    li $v0, 8
    move $a0, $t7
    la $a1, 63
    syscall
    move $a0, $t5
    move $a1, $t7 
    jal strcmp
    move $t8, $v0
    beqz $t8, end
    move $t4, $t7

    bldglpa:
    li $t6, 10
    lb $t3, 0($t4)
    beq $t6, $t3, bldgsplash
    addi $t4, $t4, 1
    j bldglpa

    bldgsplash:
    sb $zero, 0($t4)
    li $v0, 4           
    la $a0, bldgsqft
    syscall
    li $v0, 5               
    syscall
    move $t0, $v0   
    li $v0, 4
    la $a0, bldgenergy
    syscall
    li $v0, 6
    syscall
    mov.s $f1, $f0              
    beq  $t0, $zero, nothingz
    mtc1 $t0, $f0
    cvt.s.w $f0, $f0
    div.s $f0, $f1, $f0
    j morebldgs

nothingz:
    l.s   $f0, zerofl

morebldgs:
    swc1 $f0, 64($t7)
    sw $zero, 68($t7)
    move $s4, $s1
    addi $s3, 1

colocandobldgs:
    lw $s5, 68($s4)
    beq $s5, $zero, fbldg
    
    move $a0, $t7
    move $a1, $s5 
    jal bdlgccc
    move $t9, $v0 
    
    loopy:
    blez $t9, putthatbldg
    lw $s4, 68($s4)
    j colocandobldgs

    fbldg:
    sw $t7, 68($s4)
    j end_colocandobldgs

    putthatbldg:
    sw $t7, 68($s4)
    sw $s5, 68($t7)

end_colocandobldgs:
    j bldgls

strcmp:
    addi $sp, $sp, -4
    sw $ra, 0($sp)

    loop:
    lbu $t1, ($a0)      
    lbu $t2, ($a1)      
    
    bnez $t1, checknotequal
    beqz $t2, done
    j notequal

    checknotequal:
    bne $t1, $t2, notequal
    addiu $a0, $a0, 1   
    addiu $a1, $a1, 1  
    j loop

    notequal:
    sub $v0, $t1, $t2   
    lw $ra, 0($sp)
    addi $sp, $sp, 4
    jr $ra

    done:
    li $v0, 0
    lw $ra, 0($sp)
    addi $sp, $sp, 4
    jr $ra

bdlgccc:
    addi $sp, $sp, -24
    sw $ra, 0($sp)
    sw $s1, 4($sp)
    sw $s6, 8($sp)
    sw $s3, 12($sp)
    sw $s4, 16($sp)
    sw $s5, 20($sp)
    move $s3, $a0
    move $s4, $a1
    lwc1 $f0, 64($s3)
    lwc1 $f1, 64($s4)
    
    c.lt.s $f0, $f1
    bc1t bldgmais
    c.eq.s $f0, $f1
    bc1f bldgmenos

    bldgbldg:
    move $a0, $s3
    move $a1, $s4 
    jal strcmp  
    move $s5, $v0 
    blez $s5, bldgmenos 
    j bldgmais

bldgmenos:
    li $v0, -1
    j cleanallll

bldgmais:
    li $v0, 1

cleanallll:
    lw $s5, 20($sp)
    lw $s4, 16($sp)
    lw $s3, 12($sp)
    lw $s6, 8($sp)
    lw $s1, 4($sp)
    lw $ra, 0($sp)
    addi $sp, $sp, 24
    jr $ra       

end:
    move $s2, $s1
    lw $s2, 68($s2)
    move $t3, $s3

blgprinting:
    beq $t3, $zero, exit
    lwc1 $f12, 64($s2)
    li $v0, 4
    move $a0, $s2
    syscall
    li $v0, 4
    la $a0, betweenb
    syscall
    li $v0, 2
    move $a0, $t4
    syscall
    li $v0, 4
    la $a0, nl
    syscall
    lw $s2, 68($s2)
    addi $t3, $t3, -1
    j blgprinting

exit:
    lw $ra, 0($sp)
    lw $s0, 4($sp)
    lw $s1, 8($sp)
    lw $s2, 12($sp)
    lw $s3, 16($sp)
    lw $s4, 20($sp)
    lw $s5, 24($sp)
    addi $sp, $sp, 28

    jr $ra