import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateTableModal } from './create-table-modal';

describe('CreateTableModal', () => {
  let component: CreateTableModal;
  let fixture: ComponentFixture<CreateTableModal>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateTableModal]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateTableModal);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
