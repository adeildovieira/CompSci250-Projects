#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct DukeBldg {
  char bldg_name[64];
  float energy_eff;
  struct DukeBldg* next;
};

void swap(struct DukeBldg* Bldg1, struct DukeBldg* Bldg2) {
  struct DukeBldg temp = *Bldg1;
  *Bldg1 = *Bldg2; 
  *Bldg2 = temp;
}

void SortingBldg(struct DukeBldg** head) {
  int sorts = 0;

  while (!sorts) {
    struct DukeBldg* current = *head;
    struct DukeBldg* prev = NULL;
    sorts = 1;

    while (current != NULL) {
      struct DukeBldg* next = current->next;
      
      if (next != NULL && (current->energy_eff < next->energy_eff || 
          (current->energy_eff == next->energy_eff &&
           strcmp(current->bldg_name, next->bldg_name) > 0))) {
        sorts = 0;
        current->next = next->next;
        next->next = current;
        
        if (prev != NULL) {
          prev->next = next;
        } else {
          *head = next;
        }
      
        current = next;
        next = current->next;
      }
      
      prev = current;
      current = next;
    }
  }
}

void ToPrintBldgandEnEff(struct DukeBldg* head) {
  while (head != NULL) {
    printf("%s %f\n", head->bldg_name, head->energy_eff);
    struct DukeBldg* temp = head;
    head = head->next;
    free(temp);
  }
}

int main(int argc, char* argv[]) {

  // If case of document:

  if (argc != 2) {
    printf("Usage: %s <input_file>\n", argv[0]);
    return 1;
  }

  FILE* inputbldgs = fopen(argv[1], "r");
  
  if (inputbldgs == NULL) {
    perror("Error opening input file");
    return 1;
  }
  
  int testChar = fgetc(inputbldgs);
  
  if (testChar == EOF) {
    if (feof(inputbldgs)) {
      printf("BUILDING FILE IS EMPTY\n");
    }
    fclose(inputbldgs);
    return EXIT_SUCCESS;
  } else {
  rewind(inputbldgs);
  }

  struct DukeBldg* head = NULL;
  struct DukeBldg* tail = NULL;

  char b_name[64];
  int sqrft;
  float eneff;

  while (1) {

    if (fscanf(inputbldgs, "%63s", b_name) != 1) {
      break;
    }

    if (strcmp(b_name, "DONE") == 0) {
      break; 
    }

    if (fscanf(inputbldgs, "%d", &sqrft) != 1 || 
        fscanf(inputbldgs, "%f", &eneff) != 1) {
      printf("Invalid input format\n");
      return 1;
    }

    struct DukeBldg* newBldg = (struct DukeBldg*)malloc(sizeof(struct DukeBldg));
    newBldg->next = NULL;

    if (sqrft != 0) {
      newBldg->energy_eff = eneff / sqrft;
    } else {
      newBldg->energy_eff = 0.0; 
    }

    strcpy(newBldg->bldg_name, b_name);

    if (head == NULL) {
      head = newBldg;
      tail = head;
    } else {
      tail->next = newBldg;
      tail = tail->next;
    }
  }
  
  if (head != NULL) {
    SortingBldg(&head);
    ToPrintBldgandEnEff(head);
  } else {
    printf("BUILDING FILE IS EMPTY\n");
  }

  fclose(inputbldgs);

  return EXIT_SUCCESS;
}