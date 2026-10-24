import {
  date,
  jsonb,
  pgTable,
  primaryKey,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

export const foodScansTable = pgTable("food_scans", {
  id: text("id").primaryKey(),
  ownerId: text("owner_id").notNull().default("demo"),
  dishName: text("dish_name").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull(),
  payload: jsonb("payload").notNull(),
});

export const hygieneAuditsTable = pgTable("hygiene_audits", {
  id: text("id").primaryKey(),
  ownerId: text("owner_id").notNull().default("demo"),
  kitchenName: text("kitchen_name").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull(),
  payload: jsonb("payload").notNull(),
});

export const nutritionProfilesTable = pgTable("nutrition_profiles", {
  profileId: text("profile_id").primaryKey(),
  payload: jsonb("payload").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull(),
});

export const mealPlansTable = pgTable("meal_plans", {
  weekOf: date("week_of", { mode: "string" }).primaryKey(),
  payload: jsonb("payload").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull(),
});

export const userMealPlansTable = pgTable(
  "user_meal_plans",
  {
    ownerId: text("owner_id").notNull().default("demo"),
    weekOf: date("week_of", { mode: "string" }).notNull(),
    payload: jsonb("payload").notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.ownerId, table.weekOf] }),
  }),
);
