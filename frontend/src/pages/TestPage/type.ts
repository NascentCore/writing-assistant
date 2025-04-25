export interface RegisterFormValues {
  username: string;
  email: string;
  password: string;
  confirmPassword?: string;
  gender?: string;
  age?: number;
}

export type TestPageProps = Record<string, never>;
